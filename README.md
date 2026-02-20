# Spotify-Tidal Migration Tool

A Python script that migrates your music library from Spotify to Tidal, including playlists and liked tracks.

## Features

- **Playlist Migration**: Transfer your Spotify playlists to Tidal with full track listings
- **Liked Tracks Migration**: Move your saved/liked tracks from Spotify to Tidal
- **Interactive Selection**: Choose exactly which playlists you want to migrate
- **Progress Tracking**: Visual progress bars for all operations
- **ISRC Matching**: Uses International Standard Recording Code for accurate track matching
- **Error Handling**: Graceful handling of tracks that can't be found on Tidal

## Prerequisites

### Required Python Packages

```bash
pip -r requirements.txt
```

### API Setup

#### Spotify API Setup
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note down your `Client ID` and `Client Secret`
4. Add a redirect URI (e.g., ``)

#### Tidal Account
- You need an active Tidal subscription
- The script uses OAuth authentication (no API keys required)

## Configuration

Create a `secrets.py` file in the same directory with your Spotify credentials:

```python
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret" 
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
```

## Usage

1. **Run the script**:
   ```bash
   python migration_tool.py
   ```

2. **Authentication**:
   - The script will prompt you to authenticate with both Spotify and Tidal
   - For Spotify: A browser window will open for OAuth authentication
   - For Tidal: Follow the OAuth simple login process

3. **Select Migration Options**:
   - Choose what you want to migrate (Playlists and/or Liked Tracks)
   - If migrating playlists, select which specific playlists to transfer

4. **Monitor Progress**:
   - Progress bars will show the migration status
   - Any tracks that can't be found on Tidal will be reported

## How It Works

### Track Matching
The script uses **ISRC (International Standard Recording Code)** to match tracks between platforms. This ensures high accuracy in finding the correct version of each song on Tidal.

### Migration Process
1. **Playlists**: Creates new playlists in Tidal with the same name and description, then adds all tracks
2. **Liked Tracks**: Adds tracks to your Tidal favorites/liked tracks

### Error Handling
- Tracks not found on Tidal are reported but don't stop the migration
- Network errors are handled gracefully with detailed error messages
- Progress continues even if individual tracks fail

## Limitations

- **Track Availability**: Not all Spotify tracks may be available on Tidal due to licensing differences
- **Rate Limits**: The script includes progress tracking but may be subject to API rate limits
- **Playlist Order**: Track order within playlists is preserved
- **Metadata**: Only basic playlist information (name, description) is transferred

## Troubleshooting

### Common Issues

**Authentication Failures**:
- Verify your Spotify credentials in `secrets.py`
- Ensure your redirect URI matches exactly
- Check your internet connection

**Tracks Not Found**:
- This is normal due to catalog differences between platforms
- The script will report which tracks couldn't be matched
- ISRC matching is used for highest accuracy

**Memory Issues with Large Libraries**:
- The script loads all data into memory
- For very large libraries (10,000+ tracks), monitor system resources

## Output

The script provides:
- Real-time progress bars for all operations
- List of tracks that couldn't be found on Tidal
- Confirmation when migration is complete

## Security Notes

- Keep your `secrets.py` file secure and don't commit it to version control
- The script uses OAuth for secure authentication
- No passwords are stored or transmitted

## License

This tool is for personal use. Respect the terms of service for both Spotify and Tidal APIs.

## Contributing

Feel free to submit issues or pull requests to improve the migration tool.

