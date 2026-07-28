
### Environment Interaction 1
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_app_descriptions())
```

```
[
 {
  "name": "api_docs",
  "description": "An app to search and explore API documentation."
 },
 {
  "name": "supervisor",
  "description": "An app to access supervisor's personal information, account credentials, addresses, payment cards, and manage the assigned task."
 },
 {
  "name": "amazon",
  "description": "An online shopping app to buy products and manage orders, returns, etc."
 },
 {
  "name": "phone",
  "description": "An app to find and manage contact information for friends, family members, etc., send and receive messages, and manage alarms."
 },
 {
  "name": "file_system",
  "description": "A file system app to create and manage files and folders."
 },
 {
  "name": "spotify",
  "description": "A music streaming app to stream songs and manage song, album and playlist libraries."
 },
 {
  "name": "venmo",
  "description": "A social payment app to send, receive and request money to and from others."
 },
 {
  "name": "gmail",
  "description": "An email app to draft, send, receive, and manage emails."
 },
 {
  "name": "splitwise",
  "description": "A bill splitting app to track and split expenses with people."
 },
 {
  "name": "simple_note",
  "description": "A note-taking app to create and manage notes"
 },
 {
  "name": "todoist",
  "description": "A task management app to manage todo lists and collaborate on them with others."
 }
]
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='api_docs'))
```

```
[
 {
  "name": "show_app_descriptions",
  "description": "Show descriptions for all apps available."
 },
 {
  "name": "show_api_descriptions",
  "description": "Show descriptions for all APIs available for a given app."
 },
 {
  "name": "show_api_doc",
  "description": "Show detailed API doc."
 },
 {
  "name": "search_api_docs",
  "description": "Search for relevant API docs."
 }
]
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='supervisor'))
```

```
[
 {
  "name": "show_active_task",
  "description": "Show the currently active task assigned to you by the supervisor."
 },
 {
  "name": "complete_task",
  "description": "Mark the currently active task as complete with the given answer."
 },
 {
  "name": "show_profile",
  "description": "Show your supervisor's profile information."
 },
 {
  "name": "show_addresses",
  "description": "Show your supervisor's addresses."
 },
 {
  "name": "show_payment_cards",
  "description": "Show your supervisor's payment_cards."
 },
 {
  "name": "show_account_passwords",
  "description": "Show your supervisor's app account passwords."
 }
]
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='amazon'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "show_product",
  "description": "Show product information based on its ID."
 },
 {
  "name": "search_sellers",
  "description": "Search for sellers with a query."
 },
 {
  "name": "show_seller",
  "description": "Show a detailed information about the seller."
 },
 {
  "name": "search_product_types",
  "description": "Search product types present in the database."
 },
 {
  "name": "show_product_feature_choices",
  "description": "Show the choices of colors, relative sizes and sellers aggregated over all products of the given product type. Because it's an aggregation, the choices may not be available for all products. If product type is not passed, it will return the choices for all products in the database."
 },
 {
  "name": "search_products",
  "description": "Search for products with a query and various filtering criteria."
 },
 {
  "name": "show_cart",
  "description": "show your cart."
 },
 {
  "name": "clear_cart",
  "description": "Clear your cart."
 },
 {
  "name": "add_product_to_cart",
  "description": "Add product by id and quantities to your cart."
 },
 {
  "name": "delete_product_from_cart",
  "description": "Remove a product from your cart."
 },
 {
  "name": "update_product_quantity_in_cart",
  "description": "Update product quantity in the user cart."
 },
 {
  "name": "apply_promo_code_to_cart",
  "description": "Apply a promo code to your cart."
 },
 {
  "name": "remove_promo_code_from_cart",
  "description": "Remove a promo code from your cart."
 },
 {
  "name": "show_wish_list",
  "description": "Get list of products in your wishlist."
 },
 {
  "name": "clear_wish_list",
  "description": "Clear wish list."
 },
 {
  "name": "add_product_to_wish_list",
  "description": "Add product by id and quantities to your wish list."
 },
 {
  "name": "delete_product_from_wish_list",
  "description": "Remove product from the user wish list."
 },
 {
  "name": "update_product_quantity_in_wish_list",
  "description": "Update product quantity in the user wish_list."
 },
 {
  "name": "move_product_from_cart_to_wish_list",
  "description": "Move product from the cart to the wish list."
 },
 {
  "name": "move_product_from_wish_list_to_cart",
  "description": "Move product from the wish list to the cart."
 },
 {
  "name": "add_gift_wrapping_to_product",
  "description": "Add gift wrapping to a product in your cart. If the product is already set to be gift wrapped, its quantity will be updated."
 },
 {
  "name": "remove_gift_wrapping_from_product",
  "description": "Remove gift wrapping from a product in your cart."
 },
 {
  "name": "show_orders",
  "description": "Show or search your past orders"
 },
 {
  "name": "place_order",
  "description": "Place an order for all the items in your cart."
 },
 {
  "name": "show_order",
  "description": "Get details of a past order."
 },
 {
  "name": "download_order_receipt",
  "description": "Download the receipt of a past order."
 },
 {
  "name": "show_payment_cards",
  "description": "Get a list of your payment_cards."
 },
 {
  "name": "add_payment_card",
  "description": "Add a new payment card."
 },
 {
  "name": "show_payment_card",
  "description": "Get details of a payment card."
 },
 {
  "name": "delete_payment_card",
  "description": "Delete payment card information."
 },
 {
  "name": "update_payment_card",
  "description": "Update payment card information."
 },
 {
  "name": "show_addresses",
  "description": "Get a list of your addresses."
 },
 {
  "name": "add_address",
  "description": "Add a new address."
 },
 {
  "name": "delete_address",
  "description": "Delete address information."
 },
 {
  "name": "update_address",
  "description": "Update address information."
 },
 {
  "name": "show_product_reviews",
  "description": "Get a list of product reviews."
 },
 {
  "name": "write_product_review",
  "description": "Write a product review."
 },
 {
  "name": "delete_product_review",
  "description": "Delete a product review."
 },
 {
  "name": "update_product_review",
  "description": "Update a product review."
 },
 {
  "name": "show_product_questions",
  "description": "Get a list of product questions."
 },
 {
  "name": "write_product_question",
  "description": "Post a question about a product."
 },
 {
  "name": "show_product_question_answers",
  "description": "Get a list of answers to a product question."
 },
 {
  "name": "write_product_question_answer",
  "description": "Write a answer to a product question."
 },
 {
  "name": "delete_product_question",
  "description": "Delete a product question."
 },
 {
  "name": "update_product_question",
  "description": "Update a product question."
 },
 {
  "name": "delete_product_question_answer",
  "description": "Delete a answer to a product question."
 },
 {
  "name": "update_product_question_answer",
  "description": "Update answer to a product question."
 },
 {
  "name": "show_returns",
  "description": "Get a list of your product returns."
 },
 {
  "name": "initiate_return",
  "description": "Initiate a product return."
 },
 {
  "name": "show_return",
  "description": "Show product return status."
 },
 {
  "name": "show_return_deliverers",
  "description": "Get a list of product return deliverers."
 },
 {
  "name": "show_prime_plans",
  "description": "Show information about prime plans available. Delivery fee is waived for prime members."
 },
 {
  "name": "show_prime_subscriptions",
  "description": "Show your prime subscription history."
 },
 {
  "name": "subscribe_prime",
  "description": "Subscribe to prime membership."
 },
 {
  "name": "download_prime_subscription_receipt",
  "description": "Download the receipt for a prime subscription."
 }
]
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='phone'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your phone number."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "show_contact_relationships",
  "description": "Get a list of all relationships available in your contact book."
 },
 {
  "name": "search_contacts",
  "description": "Search your contact book for relatives' information."
 },
 {
  "name": "add_contact",
  "description": "Add a new contact."
 },
 {
  "name": "delete_contact",
  "description": "Delete contact information."
 },
 {
  "name": "update_contact",
  "description": "Update contact information."
 },
 {
  "name": "show_text_message_window",
  "description": "Show text messages with a contact around a given date and time."
 },
 {
  "name": "search_text_messages",
  "description": "Show or search your text messages."
 },
 {
  "name": "show_text_message",
  "description": "Show text message details."
 },
 {
  "name": "delete_text_message",
  "description": "Delete a text message."
 },
 {
  "name": "send_text_message",
  "description": "Send a text message on the given phone number."
 },
 {
  "name": "show_alarms",
  "description": "Get a list of alarms."
 },
 {
  "name": "create_alarm",
  "description": "Create a new alarm."
 },
 {
  "name": "show_alarm",
  "description": "Show alarm details."
 },
 {
  "name": "delete_alarm",
  "description": "Delete an alarm."
 },
 {
  "name": "update_alarm",
  "description": "Update an alarm's settings."
 },
 {
  "name": "show_voice_message_window",
  "description": "Show voice messages with a contact around a given date and time."
 },
 {
  "name": "search_voice_messages",
  "description": "Show or search text voice_messages between the user and a contact."
 },
 {
  "name": "show_voice_message",
  "description": "Show voice message details."
 },
 {
  "name": "delete_voice_message",
  "description": "Delete a voice message."
 },
 {
  "name": "send_voice_message",
  "description": "Send a voice message on the given phone number."
 },
 {
  "name": "get_current_date_and_time",
  "description": "Show current date and time."
 }
]
```


### Environment Interaction 6
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='file_system'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "show_directory",
  "description": "Show a list of files and/or sub-directories, optionally recursively, in a directory."
 },
 {
  "name": "create_directory",
  "description": "Create a directory if it does not exist, optionally recursively."
 },
 {
  "name": "delete_directory",
  "description": "Delete a directory with its sub-directories and files."
 },
 {
  "name": "directory_exists",
  "description": "Check if a directory exists."
 },
 {
  "name": "show_file",
  "description": "Show a file's content and other details, if it exists."
 },
 {
  "name": "create_file",
  "description": "Create a new file with the given content."
 },
 {
  "name": "delete_file",
  "description": "Delete a file."
 },
 {
  "name": "update_file",
  "description": "Update a file's content."
 },
 {
  "name": "file_exists",
  "description": "Check if a file exists."
 },
 {
  "name": "copy_file",
  "description": "Copy a file to another location."
 },
 {
  "name": "move_file",
  "description": "Move a file to another location."
 },
 {
  "name": "copy_directory",
  "description": "Copy a directory to another location."
 },
 {
  "name": "move_directory",
  "description": "Move a directory to another location."
 },
 {
  "name": "compress_directory",
  "description": "Compress a directory."
 },
 {
  "name": "decompress_file",
  "description": "Decompress a compressed file."
 }
]
```


### Environment Interaction 7
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='spotify'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "show_genres",
  "description": "Show the list of all music genres."
 },
 {
  "name": "search_songs",
  "description": "Search for songs with a query."
 },
 {
  "name": "show_song",
  "description": "Get details of a specific song."
 },
 {
  "name": "show_song_privates",
  "description": "Show information about the song that is private to the user."
 },
 {
  "name": "like_song",
  "description": "Like a song."
 },
 {
  "name": "unlike_song",
  "description": "Unlike a song."
 },
 {
  "name": "show_liked_songs",
  "description": "Get a list of songs you have liked."
 },
 {
  "name": "search_albums",
  "description": "Search for albums with a query."
 },
 {
  "name": "show_album",
  "description": "Get details of a specific album."
 },
 {
  "name": "show_album_privates",
  "description": "Show information about the album that is private to the user."
 },
 {
  "name": "like_album",
  "description": "Like a album."
 },
 {
  "name": "unlike_album",
  "description": "Unlike a album."
 },
 {
  "name": "show_liked_albums",
  "description": "Get a list of albums you have liked."
 },
 {
  "name": "show_playlist_library",
  "description": "Get a list of playlists in the user's playlist library."
 },
 {
  "name": "search_playlists",
  "description": "Search for playlists with a query. It will search over all public playlists and your own private playlists."
 },
 {
  "name": "create_playlist",
  "description": "Create a new playlist."
 },
 {
  "name": "show_playlist",
  "description": "Get detailed information about a specific playlist. You can view your own playlists or others' playlists if they are public."
 },
 {
  "name": "delete_playlist",
  "description": "Delete a playlist."
 },
 {
  "name": "update_playlist",
  "description": "Update a playlist title or privacy."
 },
 {
  "name": "show_playlist_privates",
  "description": "Show information about the playlist that is private to the user."
 },
 {
  "name": "like_playlist",
  "description": "Like a playlist."
 },
 {
  "name": "unlike_playlist",
  "description": "Unlike a playlist."
 },
 {
  "name": "show_liked_playlists",
  "description": "Get a list of playlists you have liked."
 },
 {
  "name": "search_artists",
  "description": "Search for artists with a query."
 },
 {
  "name": "show_artist",
  "description": "Get details of a specific artist."
 },
 {
  "name": "show_artist_following",
  "description": "Show if the user is following the artist."
 },
 {
  "name": "show_song_library",
  "description": "Get a list of songs in the user's song library."
 },
 {
  "name": "add_song_to_library",
  "description": "Add a song to the user's song library."
 },
 {
  "name": "remove_song_from_library",
  "description": "Remove a song from the user's song library."
 },
 {
  "name": "show_album_library",
  "description": "Get a list of albums in the user's album library."
 },
 {
  "name": "add_album_to_library",
  "description": "Add an album to the user's album library."
 },
 {
  "name": "remove_album_from_library",
  "description": "Remove an album from the user's album library."
 },
 {
  "name": "add_song_to_playlist",
  "description": "Add a song to a playlist."
 },
 {
  "name": "remove_song_from_playlist",
  "description": "Remove a song from a playlist."
 },
 {
  "name": "show_downloaded_songs",
  "description": "Get a list of downloaded songs."
 },
 {
  "name": "download_song",
  "description": "Download a song."
 },
 {
  "name": "remove_downloaded_song",
  "description": "Remove a song from downloads."
 },
 {
  "name": "show_following_artists",
  "description": "Get a list of artists the user is following."
 },
 {
  "name": "follow_artist",
  "description": "Follow an artist."
 },
 {
  "name": "unfollow_artist",
  "description": "Unfollow an artist."
 },
 {
  "name": "show_song_reviews",
  "description": "Get a list of reviews for a song."
 },
 {
  "name": "review_song",
  "description": "Rate or review a song."
 },
 {
  "name": "show_song_review",
  "description": "Show a song review."
 },
 {
  "name": "delete_song_review",
  "description": "Delete a song review."
 },
 {
  "name": "update_song_review",
  "description": "Update a song review."
 },
 {
  "name": "show_album_reviews",
  "description": "Get a list of reviews for an album."
 },
 {
  "name": "review_album",
  "description": "Rate or review an album."
 },
 {
  "name": "show_album_review",
  "description": "Show an album review."
 },
 {
  "name": "delete_album_review",
  "description": "Delete an album review."
 },
 {
  "name": "update_album_review",
  "description": "Update an album review."
 },
 {
  "name": "show_playlist_reviews",
  "description": "Show a list of reviews for your playlist or others' public playlist."
 },
 {
  "name": "review_playlist",
  "description": "Rate or review a playlist."
 },
 {
  "name": "show_playlist_review",
  "description": "Show a playlist review."
 },
 {
  "name": "delete_playlist_review",
  "description": "Delete a playlist review."
 },
 {
  "name": "update_playlist_review",
  "description": "Update a playlist review."
 },
 {
  "name": "show_payment_cards",
  "description": "Get a list of users payment cards."
 },
 {
  "name": "add_payment_card",
  "description": "Add a new payment card."
 },
 {
  "name": "show_payment_card",
  "description": "Get details of a payment card."
 },
 {
  "name": "delete_payment_card",
  "description": "Delete payment card information."
 },
 {
  "name": "update_payment_card",
  "description": "Update payment card information."
 },
 {
  "name": "show_current_song",
  "description": "Show details of the current song on the queue."
 },
 {
  "name": "play_music",
  "description": "Play music based on various criteria. You can pass, at most, any one of queue_position, song_id, album_id or playlist_id. If one of song_id, album_id or playlist_id is passed, that song, album or playlist will be added to the queue and played. Otherwise, the queue will remain unchanged. If queue_position is passed, the song at that position in the queue will be played. If none is passed, the current song in the queue will be played."
 },
 {
  "name": "pause_music",
  "description": "Pause the currently playing song."
 },
 {
  "name": "previous_song",
  "description": "Go to the previous song in the song queue."
 },
 {
  "name": "next_song",
  "description": "Go to the next song in the song queue."
 },
 {
  "name": "move_song_in_queue",
  "description": "Move a song in the queue to a new position."
 },
 {
  "name": "seek_song",
  "description": "Seek the current song to the given number of seconds."
 },
 {
  "name": "loop_song",
  "description": "Set whether to loop the current song."
 },
 {
  "name": "shuffle_song_queue",
  "description": "Shuffle songs in the music player queue."
 },
 {
  "name": "show_song_queue",
  "description": "Get the music player song queue. Songs are played in the order of the queue in a cycle."
 },
 {
  "name": "add_to_queue",
  "description": "Add a song, album or playlist to the music player song queue."
 },
 {
  "name": "clear_song_queue",
  "description": "Clear the music player song queue."
 },
 {
  "name": "remove_song_from_queue",
  "description": "Remove a song at the given position from the music player song queue."
 },
 {
  "name": "show_volume",
  "description": "Get the volume level of the music player."
 },
 {
  "name": "set_volume",
  "description": "Set the volume level of the music player."
 },
 {
  "name": "show_recommendations",
  "description": "Get personalized song recommendations for the user."
 },
 {
  "name": "show_premium_plans",
  "description": "Show information about premium plans available."
 },
 {
  "name": "show_premium_subscriptions",
  "description": "Show your premium subscription history."
 },
 {
  "name": "subscribe_premium",
  "description": "Subscribe to premium membership."
 },
 {
  "name": "download_premium_subscription_receipt",
  "description": "Download the receipt for a premium subscription."
 }
]
```


### Environment Interaction 8
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='venmo'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user, including your friendship status with them."
 },
 {
  "name": "search_users",
  "description": "Search Venmo users by name or email address."
 },
 {
  "name": "search_friends",
  "description": "Search your or others' friends by name or email address."
 },
 {
  "name": "add_friend",
  "description": "Add a friend to your friend list."
 },
 {
  "name": "remove_friend",
  "description": "Remove a friend from your friend list."
 },
 {
  "name": "show_venmo_balance",
  "description": "Show your Venmo balance."
 },
 {
  "name": "add_to_venmo_balance",
  "description": "Add money to your Venmo balance."
 },
 {
  "name": "withdraw_from_venmo_balance",
  "description": "Withdraw money from your Venmo balance."
 },
 {
  "name": "show_bank_transfer_history",
  "description": "Show histroy of money transfer from Venmo to payment card and vice versa."
 },
 {
  "name": "download_bank_transfer_receipt",
  "description": "Download the receipt of money transfer from Venmo to payment card or vice versa."
 },
 {
  "name": "show_transaction",
  "description": "Show transaction details."
 },
 {
  "name": "update_transaction",
  "description": "Update transaction information."
 },
 {
  "name": "show_transactions",
  "description": "Get a list of your transactions."
 },
 {
  "name": "create_transaction",
  "description": "Send money to a user."
 },
 {
  "name": "download_transaction_receipt",
  "description": "Download the receipt of a transaction (money sent from one user to another)."
 },
 {
  "name": "like_transaction",
  "description": "Like a transaction."
 },
 {
  "name": "unlike_transaction",
  "description": "Unlike a transaction."
 },
 {
  "name": "show_transaction_comments",
  "description": "Get a list of transaction comments."
 },
 {
  "name": "create_transaction_comment",
  "description": "Create a new transaction comment."
 },
 {
  "name": "show_transaction_comment",
  "description": "Show detailed information about a transaction comment."
 },
 {
  "name": "delete_transaction_comment",
  "description": "Delete a transaction comment."
 },
 {
  "name": "update_transaction_comment",
  "description": "Update a transaction comment."
 },
 {
  "name": "like_transaction_comment",
  "description": "Like a transaction comment."
 },
 {
  "name": "unlike_transaction_comment",
  "description": "Unlike a previously liked transaction comment."
 },
 {
  "name": "show_payment_card",
  "description": "Get details of a payment card."
 },
 {
  "name": "delete_payment_card",
  "description": "Delete payment card information."
 },
 {
  "name": "update_payment_card",
  "description": "Update payment card information."
 },
 {
  "name": "show_payment_cards",
  "description": "Get a list of users payment cards."
 },
 {
  "name": "add_payment_card",
  "description": "Add a new payment card."
 },
 {
  "name": "show_received_payment_requests",
  "description": "Get a list of payment requests you have received from others."
 },
 {
  "name": "show_sent_payment_requests",
  "description": "Get a list of payment requests you have sent to others."
 },
 {
  "name": "create_payment_request",
  "description": "Send a payment request."
 },
 {
  "name": "delete_payment_request",
  "description": "Delete a payment request."
 },
 {
  "name": "update_payment_request",
  "description": "Update payment request information."
 },
 {
  "name": "approve_payment_request",
  "description": "Approve a payment request."
 },
 {
  "name": "deny_payment_request",
  "description": "Deny a payment request."
 },
 {
  "name": "remind_payment_request",
  "description": "Send a reminder to a user via notification about this payment request."
 },
 {
  "name": "show_social_feed",
  "description": "Show your social feed (transactions of your friends)."
 },
 {
  "name": "show_notifications",
  "description": "Get a list of your notifications."
 },
 {
  "name": "delete_notifications",
  "description": "Delete all of your notifications."
 },
 {
  "name": "mark_notifications",
  "description": "Mark all notifications as read or unread."
 },
 {
  "name": "show_notifications_count",
  "description": "Get the count of your notifications."
 },
 {
  "name": "delete_notification",
  "description": "Delete a notification."
 },
 {
  "name": "mark_notification",
  "description": "Mark a notification as read or unread."
 }
]
```


### Environment Interaction 9
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='gmail'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "search_users",
  "description": "Search Gmail users by name or email address."
 },
 {
  "name": "show_inbox_threads",
  "description": "Show or search email threads you have received. This will not show detailed information about emails within the thread."
 },
 {
  "name": "show_outbox_threads",
  "description": "Show or search email threads you have sent. This will not show detailed information about emails within the thread."
 },
 {
  "name": "show_archived_threads",
  "description": "Show or search email threads you have archived. This will not show detailed information about emails within the thread."
 },
 {
  "name": "show_spam_threads",
  "description": "Show or search email threads that have been marked as spam. This will not show detailed information about emails within the thread."
 },
 {
  "name": "show_category_sizes",
  "description": "Show the number of email threads in each category of inbox, outbox, archived, spam, and the number of unscheduled and scheduled email drafts."
 },
 {
  "name": "show_thread",
  "description": "Show detailed information about a given email thread, including emails and drafts within it."
 },
 {
  "name": "delete_thread",
  "description": "Delete an email thread."
 },
 {
  "name": "show_email",
  "description": "Show detailed information about a given email."
 },
 {
  "name": "label_thread",
  "description": "Label an email thread."
 },
 {
  "name": "unlabel_thread",
  "description": "Remove label from an email thread."
 },
 {
  "name": "mark_thread_read",
  "description": "Mark an email thread as read."
 },
 {
  "name": "mark_thread_unread",
  "description": "Mark an email thread as unread."
 },
 {
  "name": "mark_thread_archived",
  "description": "Mark an email thread as archived."
 },
 {
  "name": "mark_thread_unarchived",
  "description": "Mark an email thread as unarchived."
 },
 {
  "name": "mark_thread_spam",
  "description": "Mark an email thread as spam."
 },
 {
  "name": "mark_thread_not_spam",
  "description": "Mark an email thread as not spam."
 },
 {
  "name": "mark_thread_starred",
  "description": "Mark an email thread as starred."
 },
 {
  "name": "mark_thread_unstarred",
  "description": "Mark an email thread as unstarred."
 },
 {
  "name": "delete_email_in_thread",
  "description": "Delete an email in a thread."
 },
 {
  "name": "send_email",
  "description": "Send a new email to one or more recipients."
 },
 {
  "name": "reply_to_email",
  "description": "Reply to an existing email in a thread."
 },
 {
  "name": "forward_email_from_thread",
  "description": "Forward an email from an email thread to one or more recipients."
 },
 {
  "name": "forward_email_thread",
  "description": "Forward entire email thread to one or more recipients."
 },
 {
  "name": "show_drafts",
  "description": "Show a list of user drafts."
 },
 {
  "name": "create_draft",
  "description": "Create a new draft."
 },
 {
  "name": "show_draft",
  "description": "Show detailed draft information."
 },
 {
  "name": "delete_draft",
  "description": "Delete draft information."
 },
 {
  "name": "update_draft",
  "description": "Update draft information."
 },
 {
  "name": "send_email_from_draft",
  "description": "Send a new email from a draft right away."
 },
 {
  "name": "download_attachment",
  "description": "Download a file attachment."
 },
 {
  "name": "upload_attachments_to_draft",
  "description": "Upload attachments to a draft."
 },
 {
  "name": "remove_attachment_from_draft",
  "description": "Delete an attachment from a draft."
 }
]
```


### Environment Interaction 10
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='splitwise'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "search_users",
  "description": "Search Splitwise users by name or email address."
 },
 {
  "name": "show_activity",
  "description": "Show a history of your expenses and payments combined."
 },
 {
  "name": "show_groups",
  "description": "Get a list of groups you are a member of."
 },
 {
  "name": "create_group",
  "description": "Create a new group of friends or family to share expenses with."
 },
 {
  "name": "show_group",
  "description": "Show group details based on its ID."
 },
 {
  "name": "delete_group",
  "description": "Delete a group you are a member of. Any member can undelete it later."
 },
 {
  "name": "update_group",
  "description": "Update group information."
 },
 {
  "name": "undelete_group",
  "description": "Undelete a group you are a member of."
 },
 {
  "name": "add_member_to_group",
  "description": "Add a member to a group."
 },
 {
  "name": "remove_member_from_group",
  "description": "Remove a member from a group."
 },
 {
  "name": "exit_group",
  "description": "Exit from a group you are a part of."
 },
 {
  "name": "regenerate_invitation_code",
  "description": "Regenerate the invitation code for a group. Anyone with this code can join the group. The old code will be invalidated."
 },
 {
  "name": "accept_group_invitation",
  "description": "Accept a group invitation shared with you by one of its members."
 },
 {
  "name": "record_expense",
  "description": "Record a new expense to share with others."
 },
 {
  "name": "download_expense_receipt_file",
  "description": "Download a receipt file attachment for an expense."
 },
 {
  "name": "attach_expense_receipt_file",
  "description": "Attach a receipt file to an expense."
 },
 {
  "name": "delete_expense_receipt_file",
  "description": "Delete the receipt file from an expense."
 },
 {
  "name": "show_expense",
  "description": "Show detailed expense information based on its ID."
 },
 {
  "name": "delete_expense",
  "description": "Mark the expense you are involved in as deleted. Anyone involved in the expense or a member of its group can undelete it later."
 },
 {
  "name": "update_expense",
  "description": "Update expense information."
 },
 {
  "name": "show_group_expenses",
  "description": "Show or search your expenses from a given group based on various criteria."
 },
 {
  "name": "show_no_group_expenses",
  "description": "Show or search your expenses that are not part of any group based on various criteria."
 },
 {
  "name": "undelete_expense",
  "description": "Restore a previously deleted expense you are involved in."
 },
 {
  "name": "show_expense_comments",
  "description": "Get a list of expense comments."
 },
 {
  "name": "post_expense_comment",
  "description": "Post a a comment on an expense."
 },
 {
  "name": "show_expense_comment",
  "description": "Get information about a comment posted on an expense."
 },
 {
  "name": "delete_expense_comment",
  "description": "Delete a comment you posted on an expense."
 },
 {
  "name": "update_expense_comment",
  "description": "Update a comment you posted on an expense."
 },
 {
  "name": "record_payment",
  "description": "Record a new payment for an expense. This only records payment on splitwise and does not move real money."
 },
 {
  "name": "download_payment_receipt_file",
  "description": "Download receipt file attachment for a payment."
 },
 {
  "name": "attach_payment_receipt_file",
  "description": "Attach a receipt file to a payment."
 },
 {
  "name": "delete_payment_receipt_file",
  "description": "Delete the receipt file from a payment."
 },
 {
  "name": "show_payment",
  "description": "Show payment details based on its ID."
 },
 {
  "name": "delete_payment",
  "description": "Mark the payment you are involved in as deleted. Anyone involved in the payment or a member of its group can undelete it later."
 },
 {
  "name": "update_payment",
  "description": "Update payment information."
 },
 {
  "name": "show_group_payments",
  "description": "Show all the payments that are part of the given group."
 },
 {
  "name": "show_no_group_payments",
  "description": "Show payments you are involved in that are not part of any group."
 },
 {
  "name": "undelete_payment",
  "description": "Restore a previously deleted payment you are involved in."
 },
 {
  "name": "show_person_balance",
  "description": "Show the amounts you and a given person owe to each other, broken down by group. The non-grouped expenses/payments will be shown as a group with ID None."
 },
 {
  "name": "show_people_balance",
  "description": "Show the aggregate amounts you owe to each person and they owe to you."
 },
 {
  "name": "show_group_balance",
  "description": "For the given group, show the detailed breakdown of amounts different members owe to each other. If group_id is not passed, show the amounts you owe to others and vice-versa for non-grouped expenses/payments."
 },
 {
  "name": "show_groups_balance",
  "description": "Show the aggregate amounts you owe to others or others owe you for each group you are member of. The non-grouped expenses/payments will be shown as a group with group_id of None."
 },
 {
  "name": "settle_up",
  "description": "Settle up outstanding balance with a user in a group. This only records payment on splitwise and does not move real money."
 },
 {
  "name": "show_payment_comments",
  "description": "Get a list of payment comments."
 },
 {
  "name": "post_payment_comment",
  "description": "Create a new payment comment."
 },
 {
  "name": "show_payment_comment",
  "description": "Get information about a comment posted on a payment."
 },
 {
  "name": "delete_payment_comment",
  "description": "Delete a comment you posted on a payment."
 },
 {
  "name": "update_payment_comment",
  "description": "Update a payment comment."
 },
 {
  "name": "show_notifications",
  "description": "Get a list of your notifications."
 },
 {
  "name": "delete_notifications",
  "description": "Delete all of your notifications."
 },
 {
  "name": "mark_notifications",
  "description": "Mark all notifications as read or unread."
 },
 {
  "name": "show_notifications_count",
  "description": "Get the count of your notifications."
 },
 {
  "name": "delete_notification",
  "description": "Delete a notification."
 },
 {
  "name": "mark_notification",
  "description": "Mark a notification as read or unread."
 }
]
```


### Environment Interaction 11
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='simple_note'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "search_notes",
  "description": "Search your notes. This will not show contents of the notes. Pinned notes will be shown first by default, except when dont_reorder_pinned is true."
 },
 {
  "name": "create_note",
  "description": "Create a new note."
 },
 {
  "name": "show_note",
  "description": "Show detailed information of a note, including its content."
 },
 {
  "name": "delete_note",
  "description": "Delete a note."
 },
 {
  "name": "update_note",
  "description": "Update a note's title, content, tags, and/or pinned status."
 },
 {
  "name": "add_content_to_note",
  "description": "Append or prepend content to a note."
 }
]
```


### Environment Interaction 12
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_descriptions(app_name='todoist'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "search_users",
  "description": "Search Todoist users by name or email address."
 },
 {
  "name": "show_projects",
  "description": "Show or search a list of your projects."
 },
 {
  "name": "create_project",
  "description": "Create a new project."
 },
 {
  "name": "show_project",
  "description": "Show project details based on its ID."
 },
 {
  "name": "delete_project",
  "description": "Delete a project."
 },
 {
  "name": "update_project",
  "description": "Update project information."
 },
 {
  "name": "show_sections",
  "description": "Get a list of sections within a project."
 },
 {
  "name": "create_section",
  "description": "Create a new section within a project."
 },
 {
  "name": "delete_section",
  "description": "Delete a section within a project."
 },
 {
  "name": "update_section",
  "description": "Update section information."
 },
 {
  "name": "remove_collaborator_from_project",
  "description": "Remove a collaborator (or self) from a project."
 },
 {
  "name": "send_project_invite",
  "description": "Invite a collaborator to join a project. They will be notified via email."
 },
 {
  "name": "accept_project_invite",
  "description": "Accept an invite to join a project using an invite code generated by a project collaborator."
 },
 {
  "name": "delete_project_invite",
  "description": "Delete a project invite that you sent or received."
 },
 {
  "name": "show_tasks",
  "description": "Get a list of tasks within a project."
 },
 {
  "name": "create_task",
  "description": "Create a new task within a project."
 },
 {
  "name": "assign_or_unassign_task",
  "description": "Assign or unassign a task to a user. If assignee_email is null, the task will be unassigned."
 },
 {
  "name": "show_task",
  "description": "Show detailed information about the task."
 },
 {
  "name": "delete_task",
  "description": "Delete a task."
 },
 {
  "name": "update_task",
  "description": "Update task information."
 },
 {
  "name": "show_sub_tasks",
  "description": "Get a list of sub_tasks within a task."
 },
 {
  "name": "create_sub_task",
  "description": "Create a new sub_task within a task."
 },
 {
  "name": "delete_sub_task",
  "description": "Delete a sub_task."
 },
 {
  "name": "update_sub_task",
  "description": "Update sub_task information."
 },
 {
  "name": "search_labels",
  "description": "Search your or task labels."
 },
 {
  "name": "create_label",
  "description": "Create a new label."
 },
 {
  "name": "show_label",
  "description": "Show label details based on its ID."
 },
 {
  "name": "delete_label",
  "description": "Delete a label."
 },
 {
  "name": "update_label",
  "description": "Update label information."
 },
 {
  "name": "add_label_to_task",
  "description": "Add a label to a task."
 },
 {
  "name": "remove_label_from_task",
  "description": "Remove a label from a task."
 },
 {
  "name": "show_task_comments",
  "description": "Get a list of task comments."
 },
 {
  "name": "post_task_comment",
  "description": "Post a comment on a task, optionally with a file attachment."
 },
 {
  "name": "show_task_comment",
  "description": "Show a task comment."
 },
 {
  "name": "delete_task_comment",
  "description": "Delete a task comment."
 },
 {
  "name": "update_task_comment",
  "description": "Update a task comment."
 },
 {
  "name": "upload_attachment",
  "description": "Upload an attachment to a task comment."
 },
 {
  "name": "download_attachment",
  "description": "Download the attachment of a task comment."
 },
 {
  "name": "delete_attachment",
  "description": "Delete an attachment of a task comment."
 },
 {
  "name": "show_notifications",
  "description": "Get a list of your notifications."
 },
 {
  "name": "delete_notifications",
  "description": "Delete all of your notifications."
 },
 {
  "name": "mark_notifications",
  "description": "Mark all notifications as read or unread."
 },
 {
  "name": "show_notifications_count",
  "description": "Get the count of your notifications."
 },
 {
  "name": "delete_notification",
  "description": "Delete a notification."
 },
 {
  "name": "mark_notification",
  "description": "Mark a notification as read or unread."
 }
]
```

