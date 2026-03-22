from secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from InquirerPy import inquirer
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import tidalapi
from tqdm import tqdm
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Suppress tidalapi's noisy "Track 'XXXXX' is unavailable" warnings
logging.getLogger("tidalapi").setLevel(logging.CRITICAL)

SCOPE = "user-library-read user-top-read playlist-read-private"
TIDAL_CREDENTIALS_FILE = Path("tidal_credentials.json")


# --- Tidal credential helpers ------------------------------------------------

def save_tidal_credentials(session: tidalapi.Session) -> None:
    """Save Tidal OAuth tokens to a local JSON file."""
    data = {
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": session.expiry_time.isoformat(),
    }
    TIDAL_CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    print(f"[✓] Tidal credentials saved to {TIDAL_CREDENTIALS_FILE}")


def load_tidal_credentials(session: tidalapi.Session) -> bool:
    """Try to restore a previous Tidal session from saved credentials."""
    if not TIDAL_CREDENTIALS_FILE.exists():
        return False

    try:
        raw = TIDAL_CREDENTIALS_FILE.read_text().strip()
        if not raw:
            TIDAL_CREDENTIALS_FILE.unlink()
            return False

        data = json.loads(raw)
        expiry = datetime.fromisoformat(data["expiry_time"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        success = session.load_oauth_session(
            token_type=data["token_type"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expiry_time=expiry,
        )
        if not success:
            return False

        session.check_login()
        session.user.favorites
        return True
    except Exception as exc:
        print(f"[!] Saved Tidal credentials are invalid or expired: {exc}")
        print("[!] Deleting credentials file – you'll need to log in again.")
        TIDAL_CREDENTIALS_FILE.unlink(missing_ok=True)
        return False


# --- Authentication ----------------------------------------------------------

def auth_spotify():
    """Spotify authentication"""
    try:
        print(f"Spotify redirect URI {SPOTIFY_REDIRECT_URI}")
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SCOPE,
            open_browser=False
        ))
        return sp
    except Exception as e:
        print(f"Spotify authentication failed: {e}")
        return None


def auth_tidal():
    """Tidal authentication with credential persistence."""
    try:
        session = tidalapi.Session()

        if load_tidal_credentials(session):
            print("[✓] Tidal: logged in with saved credentials.")
            return session

        print("\n" + "=" * 60)
        print("  Tidal: open the link below in your browser to log in.")
        print("=" * 60)
        session.login_oauth_simple()

        if session.check_login():
            print("[✓] Tidal: login successful!")
            save_tidal_credentials(session)
            return session
        else:
            print("[✗] Tidal: login failed.")
            return None
    except Exception as e:
        print(f"Tidal authentication failed: {e}")
        return None


# --- Spotify helpers ---------------------------------------------------------

def get_all_user_playlists_from_spotify(sp):
    """reading all Spotify playlists from user"""
    playlists = []
    limit = 50
    offset = 0

    first_results = sp.current_user_playlists(limit=limit, offset=offset)
    total_playlists = first_results['total']
    playlists.extend(first_results['items'])

    with tqdm(total=total_playlists, desc="Loading Spotify playlists", unit="playlists") as pbar:
        pbar.update(len(first_results['items']))
        offset += limit

        while True:
            results = sp.current_user_playlists(limit=limit, offset=offset)
            playlists.extend(results['items'])
            if results['next']:
                offset += limit
            else:
                break

    return playlists


def get_all_tracks_from_playlist_from_spotify(sp, pl):
    """Reading all Spotify tracks from playlist.
    Tries with market='from_token' first, falls back without it for
    playlists owned by other users (which return 403)."""

    def _fetch(market=None):
        tracks = []
        limit = 50
        offset = 0
        kwargs = {
            'playlist_id': pl['id'],
            'limit': limit,
            'offset': offset,
            'additional_types': ['track'],
        }
        if market:
            kwargs['market'] = market

        first_results = sp.playlist_tracks(**kwargs)
        total_tracks = first_results['total']
        tracks.extend(first_results['items'])

        with tqdm(total=total_tracks, desc=f"  Reading '{pl['name']}'", unit="tracks") as pbar:
            pbar.update(len(first_results['items']))
            offset += limit

            while True:
                kwargs['offset'] = offset
                results = sp.playlist_tracks(**kwargs)
                tracks.extend(results['items'])
                if results['next']:
                    offset += limit
                else:
                    break

        return tracks

    # Try with market first (gives full track data including external_ids)
    try:
        return _fetch(market='from_token')
    except Exception:
        pass

    # Fallback: without market (works for playlists from other users)
    try:
        return _fetch(market=None)
    except Exception as e:
        print(f"    [!] Could not read playlist '{pl['name']}': {e}")
        return []


def get_all_liked_tracks_from_spotify(sp):
    """reading all Spotify liked tracks"""
    tracks = []
    limit = 50
    offset = 0

    first_results = sp.current_user_saved_tracks(limit=limit, offset=offset)
    total_tracks = first_results['total']
    tracks.extend(first_results['items'])

    with tqdm(total=total_tracks, desc="Loading liked tracks", unit="tracks") as pbar:
        pbar.update(len(first_results['items']))
        offset += limit

        while first_results['next']:
            results = sp.current_user_saved_tracks(limit=limit, offset=offset)
            tracks.extend(results['items'])
            pbar.update(len(results['items']))

            if results['next']:
                offset += limit
            else:
                break

    tracks.reverse()
    return tracks


# --- Tidal helpers -----------------------------------------------------------

def get_existing_tidal_playlists(ts):
    """Load all existing playlists from the Tidal account.
    Returns a dict mapping lowercase playlist name -> playlist object."""
    try:
        playlists = ts.user.playlist_and_favorite_playlists()
        return {pl.name.lower(): pl for pl in playlists if hasattr(pl, 'name')}
    except Exception:
        return {}


def find_or_create_tidal_playlist(ts, name, description, existing_playlists):
    """Reuse an existing Tidal playlist with the same name, or create a new one."""
    key = name.lower()
    if key in existing_playlists:
        existing = existing_playlists[key]
        print(f"    → Found existing Tidal playlist '{existing.name}', reusing it.")
        return existing

    playlist = ts.user.create_playlist(name, description)
    print(f"    → Created new Tidal playlist '{name}'")
    return playlist


def copy_playlist_from_spotify_to_tidal(sp, sp_pl, ts, existing_tidal_playlists):
    """Copy a single playlist from Spotify to Tidal.
    Returns (migrated, skipped, not_found) counts."""
    print(f"\n  Playlist: '{sp_pl['name']}'")

    # 1) Read tracks from Spotify FIRST (before creating anything on Tidal)
    pl_tracks = get_all_tracks_from_playlist_from_spotify(sp, sp_pl)
    if not pl_tracks:
        print(f"    ⊘ No tracks found – skipping playlist.")
        return 0, 0, 0

    # 2) Find existing or create Tidal playlist
    tidal_pl = find_or_create_tidal_playlist(
        ts,
        sp_pl['name'],
        sp_pl.get('description') or "",
        existing_tidal_playlists,
    )

    # 3) Get existing track IDs in Tidal playlist to avoid duplicates
    existing_track_isrcs = set()
    try:
        existing_tracks = tidal_pl.tracks()
        for t in existing_tracks:
            if hasattr(t, 'isrc') and t.isrc:
                existing_track_isrcs.add(t.isrc.upper())
    except Exception:
        pass

    # 4) Migrate tracks
    migrated = 0
    skipped = []
    not_found = []
    already_exists = 0

    for track in tqdm(pl_tracks, desc=f"  Migrating tracks", unit="tracks"):
        try:
            t = track.get('track') or track.get('item')
            if t is None:
                skipped.append("Unknown (unavailable)")
                continue

            track_name = t.get('name', '?')
            artist_name = t['artists'][0]['name'] if t.get('artists') else '?'

            if track.get('is_local', False):
                skipped.append(f"{track_name} – {artist_name} (local file)")
                continue

            isrc = None
            external_ids = t.get('external_ids')
            if external_ids and isinstance(external_ids, dict):
                isrc = external_ids.get('isrc')

            if not isrc:
                skipped.append(f"{track_name} – {artist_name} (no ISRC)")
                continue

            # Skip if track is already in the Tidal playlist
            if isrc.upper() in existing_track_isrcs:
                already_exists += 1
                continue

            if tidal_pl.add_by_isrc(isrc):
                migrated += 1
            else:
                not_found.append(f"{track_name} – {artist_name}")
        except Exception as e:
            skipped.append(f"{track_name if 't' in dir() and t else '?'} (error: {e})")

    # --- Summary for this playlist ---
    total = len(pl_tracks)
    print(f"\n  ✓ '{sp_pl['name']}': {migrated}/{total} tracks migrated", end="")
    if already_exists:
        print(f" ({already_exists} already existed)", end="")
    print()
    if not_found:
        print(f"    ✗ Not found on Tidal ({len(not_found)}):")
        for name in not_found:
            print(f"      - {name}")
    if skipped:
        print(f"    ⊘ Skipped ({len(skipped)}):")
        for name in skipped:
            print(f"      - {name}")

    return migrated, len(skipped), len(not_found)


def like_track_by_isrc_in_tidal(ts, isrc, name):
    if not ts.user.favorites.add_track_by_isrc(isrc):
        return False
    return True


# --- Main --------------------------------------------------------------------

def main():
    """Start"""
    print("Welcome to the Spotify ➜ Tidal Migration Tool!")

    # --- Authenticate Spotify ---
    sp = auth_spotify()
    if sp is None:
        print("Spotify authentication failed - Exiting")
        return

    try:
        sp_user = sp.current_user()
        print(f"Spotify signed in as: {sp_user['display_name']}")
    except Exception as e:
        print(f"Spotify session error: {e}")
        return

    # --- Authenticate Tidal ---
    ts = auth_tidal()
    if ts is None:
        print("Tidal authentication failed - Exiting")
        return

    # --- Select what to migrate ---
    options = inquirer.checkbox(
        message="What would you like to migrate?",
        choices=[
            {"name": "Playlists", "value": "playlists"},
            {"name": "Liked Tracks", "value": "liked"},
        ],
        instruction="(Use space to select, enter to confirm)",
    ).execute()

    if not options:
        print("Nothing selected - Exiting")
        return

    migrations = {
        'playlists': [],
        'liked': [],
    }

    if "playlists" in options:
        try:
            playlists = get_all_user_playlists_from_spotify(sp)

            choices = [
                {"name": f"{pl['name']} ({pl.get('tracks', {}).get('total', '?')} Tracks)",
                 "value": pl}
                for pl in playlists
                if pl is not None
            ]

            selected_playlists = inquirer.checkbox(
                message="Which playlists do you want to migrate?",
                choices=choices,
                instruction="(Use space to select, enter to confirm)",
            ).execute()

            migrations['playlists'] = selected_playlists
        except Exception as e:
            print(f"Error at selecting playlists: {e}")
            return

    if "liked" in options:
        try:
            migrations['liked'] = get_all_liked_tracks_from_spotify(sp)
        except Exception as e:
            print(f"Error at reading liked tracks: {e}")
            return

    print("\n" + "=" * 60)
    print("  Starting migration")
    print("=" * 60)

    # --- Load existing Tidal playlists (for reuse & deduplication) ---
    existing_tidal_playlists = {}
    if migrations['playlists']:
        print("\nLoading existing Tidal playlists ...")
        existing_tidal_playlists = get_existing_tidal_playlists(ts)
        if existing_tidal_playlists:
            print(f"  Found {len(existing_tidal_playlists)} existing Tidal playlist(s).")

    # --- Migrate playlists ---
    if migrations['playlists']:
        total_migrated = 0
        total_skipped = 0
        total_not_found = 0

        for pl in migrations['playlists']:
            try:
                m, s, n = copy_playlist_from_spotify_to_tidal(
                    sp, pl, ts, existing_tidal_playlists)
                total_migrated += m
                total_skipped += s
                total_not_found += n
            except Exception as e:
                print(f"\n  ✗ Error at playlist '{pl['name']}': {e}")

        print(f"\n{'=' * 60}")
        print(f"  Playlist migration complete!")
        print(f"    Playlists: {len(migrations['playlists'])}")
        print(f"    Tracks migrated: {total_migrated}")
        print(f"    Not found on Tidal: {total_not_found}")
        print(f"    Skipped: {total_skipped}")
        print(f"{'=' * 60}")

    # --- Migrate liked tracks ---
    if migrations['liked']:
        print("\nMigrating liked tracks ...")
        migrated = 0
        not_found = []
        skipped = []

        for like in tqdm(migrations['liked'], desc="Migrating liked tracks", unit="tracks"):
            try:
                t = like.get('track') or like.get('item')
                if t is None:
                    continue

                track_name = t.get('name', '?')
                artist_name = t['artists'][0]['name'] if t.get('artists') else '?'

                isrc = None
                external_ids = t.get('external_ids')
                if external_ids and isinstance(external_ids, dict):
                    isrc = external_ids.get('isrc')

                if not isrc:
                    skipped.append(f"{track_name} – {artist_name} (no ISRC)")
                    continue

                if like_track_by_isrc_in_tidal(ts, isrc, track_name):
                    migrated += 1
                else:
                    not_found.append(f"{track_name} – {artist_name}")
            except Exception as e:
                skipped.append(f"{t.get('name', '?') if t else '?'} (error: {e})")

        print(f"\n{'=' * 60}")
        print(f"  Liked tracks migration complete!")
        print(f"    Migrated: {migrated}/{len(migrations['liked'])}")
        if not_found:
            print(f"    Not found on Tidal ({len(not_found)}):")
            for name in not_found:
                print(f"      - {name}")
        if skipped:
            print(f"    Skipped ({len(skipped)}):")
            for name in skipped:
                print(f"      - {name}")
        print(f"{'=' * 60}")

    print("\n✓ Migration done!")


if __name__ == "__main__":
    main()