# import spotipy
# from volume.config.delo_config import client_id, client_secret, redirect_uri

# scope = 'user-read-recently-played'
# # Аутентификация
# scope = 'user-read-recently-played'  # Разрешение на доступ к недавно прослушанным трекам
# sp = spotipy.Spotify(
#     auth_manager=spotipy.oauth2.SpotifyOAuth(
#         client_id=client_id,
#         client_secret=client_secret,
#         redirect_uri=redirect_uri,
#         scope=scope
#     )
# )

# # Получение истории прослушиваний
# results = sp.current_user_recently_played(limit=50)

# print(results)
