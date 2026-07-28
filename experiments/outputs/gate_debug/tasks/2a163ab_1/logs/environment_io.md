
### Environment Interaction 1
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_descriptions(app_name='phone')
```

```
Execution successful.
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_doc(app_name='phone', api_name='list_contacts')
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    apis.api_docs.show_api_doc(app_name='phone', api_name='list_contacts')
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: Response status code is 422:
{"message":"No APIs with name list_contacts found for the phone app. Check the api and app name again."}
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_doc(app_name='phone', api_name='list_contact_groups')
```

```
Execution failed. Traceback:
  File "<python-input>", line 1, in <module>
    apis.api_docs.show_api_doc(app_name='phone', api_name='list_contact_groups')
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: Response status code is 422:
{"message":"No APIs with name list_contact_groups found for the phone app. Check the api and app name again."}
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
apis.api_docs.show_api_doc(app_name='phone', api_name='search_contacts')
```

```
Execution successful.
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
apis.supervisor.show_profile()
```

```
Execution successful.
```


### Environment Interaction 6
----------------------------------------------------------------------------
```python
apis.supervisor.show_account_passwords()
```

```
Execution successful.
```

