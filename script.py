from secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from InquirerPy import inquirer
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import tidalapi
from tqdm import tqdm

SCOPE = "user-library-read user-top-read playlist-read-private"


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
    """Tidal authentication"""
    try:
        ts = tidalapi.Session()
        ts.login_oauth_simple()
        return ts
    except Exception as e:
        print(f"Tidal authentication failed: {e}")
        return None


def get_all_user_playlists_from_spotify(sp):
    """reading all Spotify playlists from user"""
    playlists = []
    limit = 50
    offset = 0

    first_results = sp.current_user_playlists(limit=limit, offset=offset)
    total_playlists = first_results['total']
    playlists.extend(first_results['items'])

    with tqdm(total=total_playlists, desc="Spotify playlists", unit="playlists") as pbar:
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
    """reading all Spotify tracks from playlist"""
    tracks = []
    limit = 50
    offset = 0

    first_results = sp.playlist_tracks(
        playlist_id=pl['id'], limit=limit, offset=offset)
    total_tracks = first_results['total']
    tracks.extend(first_results['items'])

    with tqdm(total=total_tracks, desc=f"{pl['name']} tracks", unit="tracks") as pbar:
        pbar.update(len(first_results['items']))
        offset += limit

        while True:
            results = sp.playlist_tracks(
                playlist_id=pl['id'], limit=limit, offset=offset)
            tracks.extend(results['items'])
            if results['next']:
                offset += limit
            else:
                break

    return tracks


def get_all_liked_tracks_from_spotify(sp):
    """reading all Spotify liked tracks"""
    tracks = []
    limit = 50
    offset = 0

    first_results = sp.current_user_saved_tracks(limit=limit, offset=offset)
    total_tracks = first_results['total']
    tracks.extend(first_results['items'])

    with tqdm(total=total_tracks, desc="Loading Spotify liked tracks", unit="tracks") as pbar:
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


def create_playlist_in_tidal(ts, name, description=""):
    print(f"CREATING PLAYLIST: {name}")
    playlist = ts.user.create_playlist(name, description)
    return playlist


def copy_playlist_from_spotify_to_tidal(sp, sp_pl, ts):
    """copy playlist from spotify to tidal"""
    new_pl = create_playlist_in_tidal(ts, sp_pl['name'], sp_pl['description'])

    pl_tracks = get_all_tracks_from_playlist_from_spotify(sp, sp_pl)
    for track in tqdm(pl_tracks, desc="migration tracks", unit="tracks"):
        try:
            if not new_pl.add_by_isrc(track['track']['external_ids']['isrc']):
                print(
                    f"Couldn't find '{track['track']['name']}' from {track['track']['artists'][0]['name']}")
        except Exception as e:
            tqdm.write(f"Error at track {track['track']['name']}: {e}")


def like_track_by_isrc_in_tidal(ts, isrc, name):
    if not ts.user.favorites.add_track_by_isrc(isrc):
        print(f"Couldn't find '{name}'")


def main():
    """Start"""
    print("Welcome to the Spotify ➜ Tidal Migration Tool!")

    try:
        sp = auth_spotify()
        ts = auth_tidal()
        if sp is None or ts is None:
            print("Authentication Failed - Exiting")
            return

        sp_user = sp.current_user()
        print(f"Spotify signed in as: {sp_user['display_name']}")
        print(f"Tidal signed in as: {ts.user.username}")
    except Exception as e:
        print(f"Error: {e}")
        return

    options = inquirer.checkbox(
        message="What would you like to migrate?",
        choices=[
            {"name": "Playlists", "value": "playlists"},
            {"name": "Liked Tracks", "value": "liked"},
            # {"name": "Albums", "value": "albums"},
            # {"name": "Followed Artists", "value": "artists"},
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

    # more selections
    if "playlists" in options:
        try:
            playlists = get_all_user_playlists_from_spotify(sp)

            choices = [
                {"name": f"{pl['name']} ({pl['tracks']['total']} Tracks)",
                 "value": pl}
                for pl in playlists
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

    print("\nStarting migration ...\n")

    # migrating
    if migrations['playlists']:
        print("Migrating playlists ...")
        for pl in tqdm(migrations['playlists'], desc="migrating playlists", unit="playlists"):
            try:
                copy_playlist_from_spotify_to_tidal(sp, pl, ts)
            except Exception as e:
                tqdm.write(f"Error at playlist {pl['name']}: {e}")

    if migrations['liked']:
        print("Migrating liked tracks ...")
        for like in tqdm(migrations['liked'], desc="migrating liked tracks", unit="tracks"):
            try:
                like_track_by_isrc_in_tidal(
                    ts, like['track']['external_ids']['isrc'], like['track']['name'])
            except Exception as e:
                tqdm.write(f"Error at track {like['track']['name']}: {e}")

    print("migration done")


if __name__ == "__main__":
    main()
