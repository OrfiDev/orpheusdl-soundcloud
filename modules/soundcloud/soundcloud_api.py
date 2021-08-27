from utils.utils import create_requests_session


class SoundCloudAPI:
    def __init__(self, access_token: str, exception):
        self.api_base = 'https://api-mobile.soundcloud.com/'
        self.access_token = access_token
        self.exception = exception
        self.s = create_requests_session()

    def _get(self, url: str, params: dict = {}):
        return self.s.get(f'{self.api_base}{url}', params=params, headers={"Authorization": "OAuth " + self.access_token}).json()

    def resolve_url(self, url: str):
        return self._get('resolve', {'identifier': url})

    def search(self, query_type: str, query: str, limit: int = 10):
        return self._get('search/' + query_type, {'limit': limit, 'top_results': 'v2', 'q': query})

    def get_playlist(self, playlist_id: str):
        playlist_data = self._get(f'playlists/soundcloud:playlists:{playlist_id}/info')

        tracks, cache_data = [], {'track': {}}
        for i in playlist_data['tracks']['collection']:
            track_id = i['urn'].split(':')[-1]
            tracks.append(track_id)
            cache_data['track'][track_id] = i

        return playlist_data['playlist'], tracks, cache_data