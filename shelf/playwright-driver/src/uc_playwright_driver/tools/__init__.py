"""Playwright tool implementations — re-exports all tool functions."""
# ruff: noqa: F401
from .browser import (
    recording_show_actions,
    screenshot,
    screenshot_element,
    scroll_page,
    scroll_to,
    set_browser,
    set_headless,
    set_viewport,
    start_recording,
    stop_recording,
    wait_for,
    wait_for_hidden,
    wait_for_url,
)
from .content import (
    get_all_texts,
    get_aria_snapshot,
    get_attribute,
    get_console_messages,
    get_html,
    get_links,
    get_page_content,
    get_page_requests,
    get_text,
    get_title,
)
from .frames import switch_to_frame, switch_to_main
from .interaction import (
    accept_dialog,
    check,
    clear,
    click,
    dismiss_dialog,
    double_click,
    drag_and_drop,
    fill,
    focus,
    hover,
    press,
    right_click,
    select_option,
    select_option_by_text,
    type_text,
    uncheck,
    upload_file,
    wait_for_download,
)
from .locators import (
    click_by_role,
    click_by_text,
    describe_element,
    fill_by_label,
    find_by_label,
    find_by_placeholder,
    find_by_role,
    find_by_test_id,
    find_by_text,
    find_interactive_elements,
)
from .navigation import current_url, go_back, go_forward, navigate, reload
from .network import abort_route, clear_route, mock_route, wait_for_response
from .script import execute_script
from .storage import (
    clear_cookies,
    clear_storage,
    get_cookies,
    get_local_storage,
    set_cookie,
    set_local_storage,
)
from .tabs import close_tab, list_tabs, new_tab, switch_tab
