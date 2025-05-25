
ValueError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/for_my_final_project/streamlit_app.py", line 164, in <module>
    st.sidebar.radio("選擇功能", pages, index=pages.index(current_page), key="page")
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/metrics_util.py", line 444, in wrapped_func
    result = non_optional_func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets/radio.py", line 275, in radio
    return self._radio(
           ~~~~~~~~~~~^
        label=label,
        ^^^^^^^^^^^^
    ...<12 lines>...
        ctx=ctx,
        ^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets/radio.py", line 394, in _radio
    serialized_value = serde.serialize(widget_state.value)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets/radio.py", line 67, in serialize
    return 0 if len(self.options) == 0 else index_(self.options, v)
                                            ~~~~~~^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/lib/options_selector_utils.py", line 60, in index_
    raise ValueError(f"{str(x)} is not in iterable")
