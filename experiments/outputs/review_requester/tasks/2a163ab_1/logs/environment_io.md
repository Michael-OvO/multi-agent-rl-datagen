
### Environment Interaction 1
----------------------------------------------------------------------------
```python
print(requester.apps)
```

```
[
 "admin",
 "amazon",
 "api_docs",
 "file_system",
 "gmail",
 "phone",
 "simple_note",
 "splitwise",
 "spotify",
 "supervisor",
 "todoist",
 "venmo"
]
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
print(requester.get('/phone/search-contacts', data={}))
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    print(requester.get('/phone/search-contacts', data={}))
          ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: Response status code is 404:
{"message":"No API named 'search-contacts' found in the phone app."}
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
print(requester.request('phone', 'search_contacts'))
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    print(requester.request('phone', 'search_contacts'))
          ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: Response status code is 401:
{"message":"You are either not authorized to access this phone API endpoint or your access token is missing, invalid or expired."}
```

