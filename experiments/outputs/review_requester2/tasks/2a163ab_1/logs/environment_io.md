
### Environment Interaction 1
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


### Environment Interaction 2
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


### Environment Interaction 3
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


### Environment Interaction 4
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

