
### Environment Interaction 1
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_descriptions(app_name='venmo')
```

```
Execution successful.
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_descriptions(app_name='venmo')
```

```
Execution successful.
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
result = apis.api_docs.show_api_descriptions(app_name='venmo')
print(repr(result))
```

```
[{'name': 'show_account', 'description': 'Show your account information. Unlike show_profile, this includes private information.'}, {'name': 'signup', 'description': 'Sign up to create account.'}, {'name': 'delete_account', 'description': 'Delete your account.'}, {'name': 'update_account_name', 'description': 'Update your first or last name in the account profile.'}, {'name': 'login', 'description': 'Login to your account.'}, {'name': 'logout', 'description': 'Logout from your account.'}, {'name': 'send_verification_code', 'description': 'Send account verification code to your email address.'}, {'name': 'verify_account', 'description': 'Verify your account using the verification code sent to your email address.'}, {'name': 'send_password_reset_code', 'description': 'Send password reset code to your email address.'}, {'name': 'reset_password', 'description': 'Reset your password using the password reset code sent to your email address.'}, {'name': 'show_profile', 'description': 'Show public profile information of a user, including your friendship status with them.'}, {'name': 'search_users', 'description': 'Search Venmo users by name or email address.'}, {'name': 'search_friends', 'description': "Search your or others' friends by name or email address."}, {'name': 'add_friend', 'description': 'Add a friend to your friend list.'}, {'name': 'remove_friend', 'description': 'Remove a friend from your friend list.'}, {'name': 'show_venmo_balance', 'description': 'Show your Venmo balance.'}, {'name': 'add_to_venmo_balance', 'description': 'Add money to your Venmo balance.'}, {'name': 'withdraw_from_venmo_balance', 'description': 'Withdraw money from your Venmo balance.'}, {'name': 'show_bank_transfer_history', 'description': 'Show histroy of money transfer from Venmo to payment card and vice versa.'}, {'name': 'download_bank_transfer_receipt', 'description': 'Download the receipt of money transfer from Venmo to payment card or vice versa.'}, {'name': 'show_transaction', 'description': 'Show transaction details.'}, {'name': 'update_transaction', 'description': 'Update transaction information.'}, {'name': 'show_transactions', 'description': 'Get a list of your transactions.'}, {'name': 'create_transaction', 'description': 'Send money to a user.'}, {'name': 'download_transaction_receipt', 'description': 'Download the receipt of a transaction (money sent from one user to another).'}, {'name': 'like_transaction', 'description': 'Like a transaction.'}, {'name': 'unlike_transaction', 'description': 'Unlike a transaction.'}, {'name': 'show_transaction_comments', 'description': 'Get a list of transaction comments.'}, {'name': 'create_transaction_comment', 'description': 'Create a new transaction comment.'}, {'name': 'show_transaction_comment', 'description': 'Show detailed information about a transaction comment.'}, {'name': 'delete_transaction_comment', 'description': 'Delete a transaction comment.'}, {'name': 'update_transaction_comment', 'description': 'Update a transaction comment.'}, {'name': 'like_transaction_comment', 'description': 'Like a transaction comment.'}, {'name': 'unlike_transaction_comment', 'description': 'Unlike a previously liked transaction comment.'}, {'name': 'show_payment_card', 'description': 'Get details of a payment card.'}, {'name': 'delete_payment_card', 'description': 'Delete payment card information.'}, {'name': 'update_payment_card', 'description': 'Update payment card information.'}, {'name': 'show_payment_cards', 'description': 'Get a list of users payment cards.'}, {'name': 'add_payment_card', 'description': 'Add a new payment card.'}, {'name': 'show_received_payment_requests', 'description': 'Get a list of payment requests you have received from others.'}, {'name': 'show_sent_payment_requests', 'description': 'Get a list of payment requests you have sent to others.'}, {'name': 'create_payment_request', 'description': 'Send a payment request.'}, {'name': 'delete_payment_request', 'description': 'Delete a payment request.'}, {'name': 'update_payment_request', 'description': 'Update payment request information.'}, {'name': 'approve_payment_request', 'description': 'Approve a payment request.'}, {'name': 'deny_payment_request', 'description': 'Deny a payment request.'}, {'name': 'remind_payment_request', 'description': 'Send a reminder to a user via notification about this payment request.'}, {'name': 'show_social_feed', 'description': 'Show your social feed (transactions of your friends).'}, {'name': 'show_notifications', 'description': 'Get a list of your notifications.'}, {'name': 'delete_notifications', 'description': 'Delete all of your notifications.'}, {'name': 'mark_notifications', 'description': 'Mark all notifications as read or unread.'}, {'name': 'show_notifications_count', 'description': 'Get the count of your notifications.'}, {'name': 'delete_notification', 'description': 'Delete a notification.'}, {'name': 'mark_notification', 'description': 'Mark a notification as read or unread.'}]
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
docs = apis.api_docs.show_api_descriptions(app_name='venmo')
print([x['name'] for x in docs])
```

```
[
 "show_account",
 "signup",
 "delete_account",
 "update_account_name",
 "login",
 "logout",
 "send_verification_code",
 "verify_account",
 "send_password_reset_code",
 "reset_password",
 "show_profile",
 "search_users",
 "search_friends",
 "add_friend",
 "remove_friend",
 "show_venmo_balance",
 "add_to_venmo_balance",
 "withdraw_from_venmo_balance",
 "show_bank_transfer_history",
 "download_bank_transfer_receipt",
 "show_transaction",
 "update_transaction",
 "show_transactions",
 "create_transaction",
 "download_transaction_receipt",
 "like_transaction",
 "unlike_transaction",
 "show_transaction_comments",
 "create_transaction_comment",
 "show_transaction_comment",
 "delete_transaction_comment",
 "update_transaction_comment",
 "like_transaction_comment",
 "unlike_transaction_comment",
 "show_payment_card",
 "delete_payment_card",
 "update_payment_card",
 "show_payment_cards",
 "add_payment_card",
 "show_received_payment_requests",
 "show_sent_payment_requests",
 "create_payment_request",
 "delete_payment_request",
 "update_payment_request",
 "approve_payment_request",
 "deny_payment_request",
 "remind_payment_request",
 "show_social_feed",
 "show_notifications",
 "delete_notifications",
 "mark_notifications",
 "show_notifications_count",
 "delete_notification",
 "mark_notification"
]
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
for name in ['login', 'show_social_feed', 'like_transaction']:
    print(name, apis.api_docs.show_api_doc(app_name='venmo', api_name=name))
```

```
login {'app_name': 'venmo', 'api_name': 'login', 'path': '/auth/token', 'method': 'POST', 'description': 'Login to your account.', 'parameters': [{'name': 'username', 'type': 'string', 'required': True, 'description': 'Your account email.', 'default': None, 'constraints': []}, {'name': 'password', 'type': 'string', 'required': True, 'description': 'Your account password.', 'default': None, 'constraints': []}], 'response_schemas': {'success': {'access_token': 'string', 'token_type': 'string'}, 'failure': {'message': 'string'}}}
show_social_feed {'app_name': 'venmo', 'api_name': 'show_social_feed', 'path': '/social_feed', 'method': 'GET', 'description': 'Show your social feed (transactions of your friends).', 'parameters': [{'name': 'access_token', 'type': 'string', 'required': True, 'description': 'Access token obtained from venmo app login.', 'default': None, 'constraints': []}, {'name': 'page_index', 'type': 'integer', 'required': False, 'description': 'The index of the page to return.', 'default': 0, 'constraints': ['value >= 0.0']}, {'name': 'page_limit', 'type': 'integer', 'required': False, 'description': 'The maximum number of results to return per page.', 'default': 5, 'constraints': ['value >= 1.0, <= 20.0']}], 'response_schemas': {'success': [{'transaction_id': 1, 'amount': 0.0, 'description': 'string', 'created_at': '2019-01-01T00:00:00', 'updated_at': '2019-01-01T00:00:00', 'private': True, 'like_count': 1, 'comment_count': 1, 'sender': {'name': 'string', 'email': 'user@example.com'}, 'receiver': {'name': 'string', 'email': 'user@example.com'}}], 'failure': {'message': 'string'}}}
like_transaction {'app_name': 'venmo', 'api_name': 'like_transaction', 'path': '/transactions/{transaction_id}/likes', 'method': 'POST', 'description': 'Like a transaction.', 'parameters': [{'name': 'transaction_id', 'type': 'integer', 'required': True, 'description': 'ID of the transaction to like.', 'default': None, 'constraints': []}, {'name': 'access_token', 'type': 'string', 'required': True, 'description': 'Access token obtained from venmo app login.', 'default': None, 'constraints': []}], 'response_schemas': {'success': {'message': 'string'}, 'failure': {'message': 'string'}}}
```


### Environment Interaction 6
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_profile())
print(apis.supervisor.show_account_passwords())
```

```
{
 "first_name": "Melissa",
 "last_name": "Bailey",
 "email": "mel.bailey@gmail.com",
 "phone_number": "3383946795",
 "birthday": "1986-08-02",
 "sex": "female"
}
[
 {
  "account_name": "amazon",
  "password": "-^+Q0iX"
 },
 {
  "account_name": "file_system",
  "password": "gwtn=GI"
 },
 {
  "account_name": "gmail",
  "password": "+*bo+du"
 },
 {
  "account_name": "phone",
  "password": "%oOZCyw"
 },
 {
  "account_name": "simple_note",
  "password": "d5x%RG4"
 },
 {
  "account_name": "splitwise",
  "password": "X(d4MNi"
 },
 {
  "account_name": "spotify",
  "password": "i}$_HBZ"
 },
 {
  "account_name": "todoist",
  "password": "$3Vx2Pe"
 },
 {
  "account_name": "venmo",
  "password": "+vNSutx"
 }
]
```


### Environment Interaction 7
----------------------------------------------------------------------------
```python
auth = apis.venmo.login(username='mel.bailey@gmail.com', password='+vNSutx')
print(auth)
```

```
{
 "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ2ZW5tbyttZWwuYmFpbGV5QGdtYWlsLmNvbSIsImV4cCI6MTY4NDQ0NjA1OX0.B34zBX595hORJCaftkDSSPtAddAftuFovXV_kaqBs9A",
 "token_type": "Bearer"
}
```


### Environment Interaction 8
----------------------------------------------------------------------------
```python
token = auth['access_token']
page = 0
all_feed = []
while True:
    batch = apis.venmo.show_social_feed(access_token=token, page_index=page, page_limit=20)
    print("page", page, "count", len(batch))
    if not batch:
        break
    all_feed.extend(batch)
    page += 1
print("total", len(all_feed))
print(all_feed[:3])
```

```
page 0 count 20
page 1 count 20
page 2 count 20
page 3 count 20
page 4 count 20
page 5 count 20
page 6 count 20
page 7 count 20
page 8 count 20
page 9 count 20
page 10 count 20
page 11 count 20
page 12 count 20
page 13 count 20
page 14 count 20
page 15 count 20
page 16 count 20
page 17 count 20
page 18 count 20
page 19 count 20
page 20 count 20
page 21 count 20
page 22 count 20
page 23 count 20
page 24 count 20
page 25 count 20
page 26 count 20
page 27 count 20
page 28 count 20
page 29 count 20
page 30 count 20
page 31 count 20
page 32 count 20
page 33 count 20
page 34 count 20
page 35 count 20
page 36 count 20
page 37 count 20
page 38 count 20
page 39 count 20
page 40 count 20
page 41 count 20
page 42 count 20
page 43 count 20
page 44 count 20
page 45 count 20
page 46 count 20
page 47 count 20
page 48 count 20
page 49 count 20
page 50 count 20
page 51 count 20
page 52 count 20
page 53 count 20
page 54 count 9
page 55 count 0
total 1089
[
 {
  "transaction_id": 8230,
  "amount": 291.0,
  "description": "Wedding Gift",
  "created_at": "2023-05-18T09:32:28",
  "updated_at": "2023-05-18T09:32:28",
  "private": false,
  "like_count": 3,
  "comment_count": 4,
  "sender": {
   "name": "Anita Burch",
   "email": "anita.burch@gmail.com"
  },
  "receiver": {
   "name": "Debra Ritter",
   "email": "de_ritt@gmail.com"
  }
 },
 {
  "transaction_id": 8219,
  "amount": 20.0,
  "description": "\ud83d\udcbbOnline Game Pass",
  "created_at": "2023-05-18T08:04:36",
  "updated_at": "2023-05-18T08:04:36",
  "private": false,
  "like_count": 3,
  "comment_count": 3,
  "sender": {
   "name": "Eric Bailey",
   "email": "eric.bailey@gmail.com"
  },
  "receiver": {
   "name": "Nicholas Weber",
   "email": "nicholas.weber@gmail.com"
  }
 },
 {
  "transaction_id": 6874,
  "amount": 33.0,
  "description": "Health Supplements",
  "created_at": "2023-05-18T08:01:10",
  "updated_at": "2023-05-18T08:01:10",
  "private": false,
  "like_count": 0,
  "comment_count": 0,
  "sender": {
   "name": "Kristin White",
   "email": "kri-powe@gmail.com"
  },
  "receiver": {
   "name": "Sabrina Brown",
   "email": "sab-brown@gmail.com"
  }
 }
]
```


### Environment Interaction 9
----------------------------------------------------------------------------
```python
from collections import Counter
dates = Counter(x['created_at'][:10] for x in all_feed)
print(dates.most_common(10))
targets = {'Anthony Harrison', 'Anita Burch', 'Nicholas Weber'}
today = max(x['created_at'][:10] for x in all_feed)
matches = [x for x in all_feed if x['created_at'][:10] == today and
           (x['sender']['name'] in targets or x['receiver']['name'] in targets)]
print("today", today, "matches", len(matches))
for x in matches:
    print(x['transaction_id'], x['created_at'], x['sender']['name'], "->", x['receiver']['name'], x['description'])
```

```
[
 [
  "2023-05-17",
  21
 ],
 [
  "2023-05-15",
  12
 ],
 [
  "2023-04-05",
  12
 ],
 [
  "2023-04-03",
  12
 ],
 [
  "2023-03-31",
  12
 ],
 [
  "2023-05-04",
  11
 ],
 [
  "2023-04-20",
  11
 ],
 [
  "2023-03-09",
  11
 ],
 [
  "2023-02-19",
  11
 ],
 [
  "2023-02-16",
  11
 ]
]
today 2023-05-18 matches 4
8230 2023-05-18T09:32:28 Anita Burch -> Debra Ritter Wedding Gift
8219 2023-05-18T08:04:36 Eric Bailey -> Nicholas Weber 💻Online Game Pass
1245 2023-05-18T06:12:19 Anita Burch -> Anthony Harrison 🛍 Outlet Shopping
7294 2023-05-18T01:54:35 Nancy Ritter -> Nicholas Weber Weekend getaway
```


### Environment Interaction 10
----------------------------------------------------------------------------
```python
results = {}
for x in matches:
    tid = x['transaction_id']
    try:
        results[tid] = apis.venmo.like_transaction(transaction_id=tid, access_token=token)
    except Exception as e:
        results[tid] = f"ERROR: {e}"
print(results)
```

```
{
 "8230": {
  "message": "Liked transaction."
 },
 "8219": {
  "message": "Liked transaction."
 },
 "1245": {
  "message": "Liked transaction."
 },
 "7294": {
  "message": "Liked transaction."
 }
}
```


### Environment Interaction 11
----------------------------------------------------------------------------
```python
apis.supervisor.complete_task(answer=None, status='success')
```

```
Execution successful.
```

