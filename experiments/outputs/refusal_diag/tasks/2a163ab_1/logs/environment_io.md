
### Environment Interaction 1
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


### Environment Interaction 2
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_doc(app_name='venmo', api_name='show_social_feed'))
```

```
{
 "app_name": "venmo",
 "api_name": "show_social_feed",
 "path": "/social_feed",
 "method": "GET",
 "description": "Show your social feed (transactions of your friends).",
 "parameters": [
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from venmo app login.",
   "default": null,
   "constraints": []
  },
  {
   "name": "page_index",
   "type": "integer",
   "required": false,
   "description": "The index of the page to return.",
   "default": 0,
   "constraints": [
    "value >= 0.0"
   ]
  },
  {
   "name": "page_limit",
   "type": "integer",
   "required": false,
   "description": "The maximum number of results to return per page.",
   "default": 5,
   "constraints": [
    "value >= 1.0, <= 20.0"
   ]
  }
 ],
 "response_schemas": {
  "success": [
   {
    "transaction_id": 1,
    "amount": 0.0,
    "description": "string",
    "created_at": "2019-01-01T00:00:00",
    "updated_at": "2019-01-01T00:00:00",
    "private": true,
    "like_count": 1,
    "comment_count": 1,
    "sender": {
     "name": "string",
     "email": "user@example.com"
    },
    "receiver": {
     "name": "string",
     "email": "user@example.com"
    }
   }
  ],
  "failure": {
   "message": "string"
  }
 }
}
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_doc(app_name='venmo', api_name='like_transaction'))
```

```
{
 "app_name": "venmo",
 "api_name": "like_transaction",
 "path": "/transactions/{transaction_id}/likes",
 "method": "POST",
 "description": "Like a transaction.",
 "parameters": [
  {
   "name": "transaction_id",
   "type": "integer",
   "required": true,
   "description": "ID of the transaction to like.",
   "default": null,
   "constraints": []
  },
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from venmo app login.",
   "default": null,
   "constraints": []
  }
 ],
 "response_schemas": {
  "success": {
   "message": "string"
  },
  "failure": {
   "message": "string"
  }
 }
}
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_profile())
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
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_account_passwords())
```

```
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


### Environment Interaction 6
----------------------------------------------------------------------------
```python
login_result = apis.venmo.login(email="mel.bailey@gmail.com", password="+vNSutx")
print(login_result)
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    login_result = apis.venmo.login(email="mel.bailey@gmail.com", password="+vNSutx")
Exception: Response status code is 422:
{"message":"Validation error. Reason: \nusername: field required"}
```


### Environment Interaction 7
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_doc(app_name='venmo', api_name='login'))
```

```
{
 "app_name": "venmo",
 "api_name": "login",
 "path": "/auth/token",
 "method": "POST",
 "description": "Login to your account.",
 "parameters": [
  {
   "name": "username",
   "type": "string",
   "required": true,
   "description": "Your account email.",
   "default": null,
   "constraints": []
  },
  {
   "name": "password",
   "type": "string",
   "required": true,
   "description": "Your account password.",
   "default": null,
   "constraints": []
  }
 ],
 "response_schemas": {
  "success": {
   "access_token": "string",
   "token_type": "string"
  },
  "failure": {
   "message": "string"
  }
 }
}
```


### Environment Interaction 8
----------------------------------------------------------------------------
```python
login_result = apis.venmo.login(username="mel.bailey@gmail.com", password="+vNSutx")
print(login_result)
```

```
{
 "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ2ZW5tbyttZWwuYmFpbGV5QGdtYWlsLmNvbSIsImV4cCI6MTY4NDQ0NjA1OX0.B34zBX595hORJCaftkDSSPtAddAftuFovXV_kaqBs9A",
 "token_type": "Bearer"
}
```


### Environment Interaction 9
----------------------------------------------------------------------------
```python
import datetime

# Prepare for pagination and matching
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ2ZW5tbyttZWwuYmFpbGV5QGdtYWlsLmNvbSIsImV4cCI6MTY4NDQ0NjA1OX0.B34zBX595hORJCaftkDSSPtAddAftuFovXV_kaqBs9A"
names_to_match = {"Anthony Harrison", "Anita Burch", "Nicholas Weber"}
today = datetime.datetime.now().date()

matching_transactions = []
page_index = 0
page_limit = 20

while True:
    feed = apis.venmo.show_social_feed(access_token=access_token, page_index=page_index, page_limit=page_limit)
    if not feed or len(feed) == 0:
        break
    for txn in feed:
        txn_date = datetime.datetime.fromisoformat(txn["created_at"]).date()
        if txn_date == today:
            sender = txn["sender"]["name"]
            receiver = txn["receiver"]["name"]
            if sender in names_to_match or receiver in names_to_match:
                matching_transactions.append(txn["transaction_id"])
    page_index += 1

print(matching_transactions)
```

```
[8230, 8219, 1245, 7294]
```


### Environment Interaction 10
----------------------------------------------------------------------------
```python
# Retry with direct literal for access_token
liked_count = 0
for txn_id in [8230, 8219, 1245, 7294]:
    result = apis.venmo.like_transaction(
        transaction_id=txn_id,
        access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ2ZW5tbyttZWwuYmFpbGV5QGdtYWlsLmNvbSIsImV4cCI6MTY4NDQ0NjA1OX0.B34zBX595hORJCaftkDSSPtAddAftuFovXV_kaqBs9A"
    )
    liked_count += 1
print(liked_count)
```

```
4
```

