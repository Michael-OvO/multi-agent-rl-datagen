
### Environment Interaction 1
----------------------------------------------------------------------------
```python
get_ipython().run_cell("print(requester.apps)")
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
get_ipython().run_cell("import os; print('OS_OK', bool(os.environ))")
```

```
OS_OK True
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
get_ipython().run_cell("print(().__class__)")
```

```
<class 'tuple'>
```

