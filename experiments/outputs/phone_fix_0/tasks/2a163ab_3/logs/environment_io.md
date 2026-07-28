
### Environment Interaction 1
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


### Environment Interaction 2
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_doc(app_name='phone', api_name='search_contacts'))
```

```
{
 "app_name": "phone",
 "api_name": "search_contacts",
 "path": "/contacts",
 "method": "GET",
 "description": "Search your contact book for relatives' information.",
 "parameters": [
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from phone app login.",
   "default": null,
   "constraints": []
  },
  {
   "name": "query",
   "type": "string",
   "required": false,
   "description": "Search query for the contacts list.",
   "default": "",
   "constraints": []
  },
  {
   "name": "relationship",
   "type": "string",
   "required": false,
   "description": "Relationship with the person in the contacts list to filter by.",
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
    "contact_id": 1,
    "first_name": "string",
    "last_name": "string",
    "email": "user@example.com",
    "phone_number": "string",
    "relationships": [
     "string"
    ],
    "birthday": "string",
    "home_address": "string",
    "work_address": "string",
    "created_at": "2019-01-01T00:00:00"
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
print(apis.supervisor.show_account_passwords())
```

```
[
 {
  "account_name": "amazon",
  "password": "y-HFh}M"
 },
 {
  "account_name": "file_system",
  "password": "fT204^N"
 },
 {
  "account_name": "gmail",
  "password": "O9rG%bf"
 },
 {
  "account_name": "phone",
  "password": "&Of)etu"
 },
 {
  "account_name": "simple_note",
  "password": "cn$Fr]h"
 },
 {
  "account_name": "splitwise",
  "password": "TccN]+b"
 },
 {
  "account_name": "spotify",
  "password": "Rlf0373"
 },
 {
  "account_name": "todoist",
  "password": "ct%y-ID"
 },
 {
  "account_name": "venmo",
  "password": "MCsW+XB"
 }
]
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_profile())
```

```
{
 "first_name": "James",
 "last_name": "Solomon",
 "email": "ja-solomon@gmail.com",
 "phone_number": "8683971586",
 "birthday": "1986-06-06",
 "sex": "male"
}
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
login_result = apis.phone.login(email="ja-solomon@gmail.com", password="&Of)etu")
print(login_result)
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    login_result = apis.phone.login(email="ja-solomon@gmail.com", password="&Of)etu")
Exception: Response status code is 422:
{"message":"Validation error. Reason: \nusername: field required"}
```


### Environment Interaction 6
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_api_doc(app_name='phone', api_name='login'))
```

```
{
 "app_name": "phone",
 "api_name": "login",
 "path": "/auth/token",
 "method": "POST",
 "description": "Login to your account.",
 "parameters": [
  {
   "name": "username",
   "type": "string",
   "required": true,
   "description": "Your account phone_number.",
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


### Environment Interaction 7
----------------------------------------------------------------------------
```python
login_result = apis.phone.login(username="8683971586", password="&Of)etu")
print(login_result)
```

```
{
 "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwaG9uZSs4NjgzOTcxNTg2IiwiZXhwIjoxNjg0NDQ0OTc5fQ.oWk9LL0lENgCLDPP5O-8V7SFmWWtx6Hi8j78xpYOJRE",
 "token_type": "Bearer"
}
```


### Environment Interaction 8
----------------------------------------------------------------------------
```python
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwaG9uZSs4NjgzOTcxNTg2IiwiZXhwIjoxNjg0NDQ0OTc5fQ.oWk9LL0lENgCLDPP5O-8V7SFmWWtx6Hi8j78xpYOJRE"

all_coworkers = []
page_index = 0
while True:
    result = apis.phone.search_contacts(
        access_token=access_token,
        relationship="coworker",
        page_index=page_index,
        page_limit=20
    )
    if not result or len(result) == 0:
        break
    for contact in result:
        full_name = f"{contact['first_name']} {contact['last_name']}".strip()
        all_coworkers.append(full_name)
    page_index += 1

print(all_coworkers)
```

```
[
 "Brandon Weber",
 "Claudia Miller",
 "Debra Ritter",
 "Kevin Blackburn",
 "Michael Burch",
 "Norman Smith",
 "Robin Burton",
 "Timothy White"
]
```

