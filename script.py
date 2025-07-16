from secrets import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, TIDAL_USERNAME, TIDAL_PASSWORD
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import tidalapi

SCOPE = "user-library-read user-top-read playlist-read-private"


def auth_spotify():
    """Spotify authentication"""
    try:
        print(f"redirect URI {SPOTIFY_REDIRECT_URI}")

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


def get_saved_tracks_from_spotify(sp, offset=0, limit=50):
    """reading saved tracks"""
    print(f"\n{'='*50}")
    print("READING SAVED TRACKS (LIKED SONGS)")
    print(f"{'='*50}")

    results = sp.current_user_saved_tracks(limit=limit, offset=offset)

    for idx, item in enumerate(results['items'], 1):
        track = item['track']
        artists = ', '.join([artist['name'] for artist in track['artists']])
        print(f"{idx:2d}. {track['name']} - {artists}")
        print(f"    Album: {track['album']['name']}")
        print(f"    Added: {item['added_at'][:10]}")
        print(f"    Item-data: {item}")
        print()


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


def get_user_playlists_from_spotify(sp, limit=20):
    """reading playlists"""
    print(f"\n{'='*50}")
    print("YOUR PLAYLISTS")
    print(f"{'='*50}")

    results = sp.current_user_playlists(limit=limit)

    for idx, playlist in enumerate(results['items'], 1):
        print(f"{idx:2d}. {playlist['name']}")
        print(f"    Tracks: {playlist['tracks']['total']}")
        print(f"    Öffentlich: {'Ja' if playlist['public'] else 'Nein'}")
        if playlist['description']:
            print(f"    Beschreibung: {playlist['description'][:100]}...")
        print(f"    Playlist-data: {playlist}")
        print()


def create_playlist_in_tidal(ts, name, description=""):
    print(f"\n{'='*50}")
    print(f"CREATING PLAYLIST: {name}")
    print(f"{'='*50}")
    playlist = ts.user.create_playlist(name, description)
    return playlist


def add_track_to_playlist_in_tidal(playlist, track_isrc):
    playlist.add_by_isrc(track_isrc)


def search_track_on_tidal(ts, query_str, type_name='tracks'):
    try:
        print(query_str)
        search = ts.search(query_str, '.Track')
        return search['tracks']
    except Exception as e:
        print(f"Execption accurred: {type(e).__name__} - {e}")
        return None


def copy_playlist_from_spotify_to_tidal(sp, sp_pl_data, ts):
    """copy playlist from spotify to tidal"""
    print(f"\n{'='*50}")
    print("COPY PLAYLIST")
    print(f"{'='*50}")

    pl_name = sp_pl_data['name']
    pl_description = sp_pl_data['description']

    # comment back in, if i want to create the playlist
    # new_pl = create_playlist_in_tidal(ts, pl_name, pl_description)

    tracks = sp.playlist_tracks(sp_pl_data['id'])

    for track in tracks['items']:
        track_name = track['track']['name']
        track_first_artist = track['track']['artists'][0]['name']
        search = search_track_on_tidal(
            ts, track_name)  # f"{track_name} {track_first_artist}")


def main():
    """Start"""
    try:
        sp = auth_spotify()
        ts = auth_tidal()
        if sp is None or ts is None:
            return

        sp_user = sp.current_user()
        print(f"Spotify signed in as: {sp_user['display_name']}")
        print(f"Tidal signed in as: {ts.user.username}")

        while True:
            print(f"\n{'='*50}")
            print("WHAT DO YOU WANT TO DISPLAY?")
            print("1. Saved tracks (liked songs)")
            print("2. Top tracks (last 6 months)")
            print("3. Top Artists (last 6 months)")
            print("4. Your playlists")
            print("5. All favorits")
            print("6. copy")
            print("0. Quit")
            print("="*50)

            choice = input("Choose your option (0-6): ")

            if choice == '1':
                get_saved_tracks_from_spotify(sp)
            elif choice == '2':
                get_top_tracks_from_spotify(sp)
            elif choice == '3':
                get_top_artists_from_spotify(sp)
            elif choice == '4':
                get_user_playlists_from_spotify(sp)
            elif choice == '5':
                get_saved_tracks_from_spotify(sp, limit=20)
                get_top_tracks_from_spotify(sp)
                get_top_artists_from_spotify(sp)
                get_user_playlists_from_spotify(sp)
            elif choice == '6':
                playlists = sp.current_user_playlists(limit=5)
                copy_playlist_from_spotify_to_tidal(
                    sp, playlists['items'][2], ts)
            elif choice == '0':
                print("Bye!")
                break
            else:
                print("Invalid selection. Please try again.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
