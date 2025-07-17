from secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, TIDAL_USERNAME, TIDAL_PASSWORD
from InquirerPy import inquirer
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import tidalapi

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
    print("Reading all Spotify playlists ...")

    playlists = []
    limit = 50
    offset = 0

    while True:
        results = sp.current_user_playlists(limit=limit, offset=offset)
        playlists.extend(results['items'])
        if results['next']:
            offset += limit
        else:
            return playlists


def get_all_tracks_from_playlist_from_spotify(sp, pl):
    """reading all Spotify tracks from playlist"""
    print(f"Reading all Spotify tracks from playlist: {pl['name']}")

    tracks = []
    limit = 100
    offset = 0

    while True:
        results = sp.playlist_tracks(
            playlist_id=pl['id'], limit=limit, offset=offset)
        tracks.extend(results['items'])
        if results['next']:
            offset += limit
        else:
            return tracks


def get_all_liked_tracks_from_spotify(sp):
    """reading all Spotify liked tracks"""
    print("Reading all Spotify liked tracks ...")

    tracks = []
    limit = 50
    offset = 0

    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        tracks.extend(results['items'])
        if results['next']:
            offset += limit
        else:
            return tracks


def get_top_tracks_from_spotify(sp, time_range='medium_term', limit=20):
    """reading top tracks"""
    time_ranges = {
        'short_term': 'LAST 4 WEEKS',
        'medium_term': 'LAST 6 MONTHS',
        'long_term': 'ALL TIME'
    }

    print(f"\n{'='*50}")
    print(f"TOP TRACKS ({time_ranges[time_range]})")
    print(f"{'='*50}")

    results = sp.current_user_top_tracks(time_range=time_range, limit=limit)

    for idx, track in enumerate(results['items'], 1):
        artists = ', '.join([artist['name'] for artist in track['artists']])
        print(f"{idx:2d}. {track['name']} - {artists}")
        print(f"    Album: {track['album']['name']}")
        print(f"    Popularität: {track['popularity']}/100")
        print(f"    Track-data: {track}")
        print()


def get_top_artists_from_spotify(sp, time_range='medium_term', limit=10):
    """reading top artists"""
    time_ranges = {
        'short_term': 'LAST 4 WEEKS',
        'medium_term': 'LAST 6 MONTHS',
        'long_term': 'ALL TIME'
    }

    print(f"\n{'='*50}")
    print(f"TOP ARTISTS ({time_ranges[time_range]})")
    print(f"{'='*50}")

    results = sp.current_user_top_artists(time_range=time_range, limit=limit)

    for idx, artist in enumerate(results['items'], 1):
        genres = ', '.join(artist['genres'][:3]
                           ) if artist['genres'] else 'Keine Genres'
        print(f"{idx:2d}. {artist['name']}")
        print(f"    Genres: {genres}")
        print(f"    Popularität: {artist['popularity']}/100")
        print(f"    Follower: {artist['followers']['total']:,}")
        print(f"    Artist-data: {artist}")
        print()


def create_playlist_in_tidal(ts, name, description=""):
    print(f"CREATING PLAYLIST: {name}")
    playlist = ts.user.create_playlist(name, description)
    return playlist


def copy_playlist_from_spotify_to_tidal(sp, sp_pl, ts):
    """copy playlist from spotify to tidal"""
    print("COPY PLAYLIST")

    new_pl = create_playlist_in_tidal(ts, sp_pl['name'], sp_pl['description'])

    pl_tracks = get_all_tracks_from_playlist_from_spotify(sp, sp_pl)
    print(
        f"{len(pl_tracks)} tracks in Spotify playlist: {sp_pl['name']}")
    for track in pl_tracks:
        if not new_pl.add_by_isrc(track['track']['external_ids']['isrc']):
            print(
                f"Couldn't find '{track['track']['name']}' from {track['track']['artists'][0]['name']}")


def like_track_by_isrc_in_tidal(ts, isrc):
    if not ts.user.favorites.add_track_by_isrc(isrc):
        print(f"Couldn't find '{isrc}'")


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

    if "liked" in options:
        migrations['liked'] = get_all_liked_tracks_from_spotify(sp)

    print("\nStarting migration ...\n")

    # migrating
    for pl in migrations['playlists']:
        print("Migrating playlists ...")
        copy_playlist_from_spotify_to_tidal(sp, pl, ts)

    for like in migrations['liked']:
        print("Migrating liked tracks ...")
        like_track_by_isrc_in_tidal(ts, like['track']['external_ids']['isrc'])
        return

    print("migration done")


if __name__ == "__main__":
    main()
