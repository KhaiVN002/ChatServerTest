import time
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

URL = "https://chatgpt.com/"

BASE_USER_DATA_DIR = Path("./chatgpt_browser_profile")

PAGE_TIMEOUT = 60000
RESPONSE_TIMEOUT = 180
POLL_INTERVAL = 0.5

INPUT_SELECTOR = 'textarea[aria-label="Chat with ChatGPT"]'
SEND_SELECTOR = "button[data-composer-submit]"

ASSISTANT_SELECTOR = 'li[data-message-role="assistant"]'
ASSISTANT_CONTENT_SELECTOR = "[data-assistant-markdown]"


# ============================================================
# GET ELEMENTS
# ============================================================

def get_input_box(page):
    input_box = page.locator(INPUT_SELECTOR)
    input_box.wait_for(state="visible", timeout=PAGE_TIMEOUT)
    return input_box


def get_send_button(page):
    button = page.locator(SEND_SELECTOR)
    button.wait_for(state="attached", timeout=PAGE_TIMEOUT)
    return button


def get_generation_state(page):
    button = page.locator(SEND_SELECTOR)

    if button.count() == 0:
        return None

    aria_label = button.get_attribute("aria-label")

    if aria_label == "Stop generating":
        return True

    if aria_label == "Send message":
        return False

    return None


# ============================================================
# WAIT FOR GENERATION
# ============================================================

def wait_for_generation(page, previous_count, timeout=RESPONSE_TIMEOUT):
    start_time = time.time()
    saw_generating = False

    while time.time() - start_time < timeout:
        state = get_generation_state(page)

        if state is True:
            saw_generating = True

        elif state is False and saw_generating:
            return

        if not saw_generating:
            messages = page.locator(ASSISTANT_SELECTOR)

            if messages.count() > previous_count:
                latest_message = messages.last

                if latest_message.get_attribute(
                    "data-message-complete"
                ) is not None:
                    return

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Generation timeout after {timeout} seconds."
    )


# ============================================================
# GET ASSISTANT RESPONSE
# ============================================================

def get_latest_assistant_text(page):
    messages = page.locator(ASSISTANT_SELECTOR)

    if messages.count() == 0:
        return ""

    latest_message = messages.last

    content = latest_message.locator(
        ASSISTANT_CONTENT_SELECTOR
    )

    if content.count() > 0:
        return content.last.inner_text().strip()

    return latest_message.inner_text().strip()


def wait_for_response(
    page,
    previous_count=0,
    timeout=RESPONSE_TIMEOUT,
):
    start_time = time.time()

    while time.time() - start_time < timeout:
        messages = page.locator(ASSISTANT_SELECTOR)

        if messages.count() > previous_count:
            latest_message = messages.last

            is_complete = (
                latest_message.get_attribute(
                    "data-message-complete"
                ) is not None
            )

            if is_complete:
                response = get_latest_assistant_text(page)

                if response:
                    return response

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Response timeout after {timeout} seconds."
    )


# ============================================================
# MAIN API
# ============================================================

def call_gpt(
    prompt: str,
    worker_id: int = 1,
    timeout: int = RESPONSE_TIMEOUT,
    headless: bool = False,
) -> str:

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string.")

    user_data_dir = BASE_USER_DATA_DIR / str(worker_id)

    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(
            user_data_dir=str(user_data_dir.resolve()),
            headless=headless,
            viewport={
                "width": 1440,
                "height": 1000,
            },
            timeout=PAGE_TIMEOUT,
        )

        try:
            page = (
                context.pages[0]
                if context.pages
                else context.new_page()
            )

            page.set_default_timeout(PAGE_TIMEOUT)

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT,
            )

            input_box = get_input_box(page)

            previous_count = page.locator(
                ASSISTANT_SELECTOR
            ).count()

            input_box.fill(prompt)

            if input_box.input_value().strip() != prompt.strip():
                raise RuntimeError(
                    "Prompt was not inserted correctly."
                )

            get_send_button(page).click()

            wait_for_generation(
                page,
                previous_count,
                timeout,
            )

            return wait_for_response(
                page,
                previous_count,
                timeout,
            )

        finally:
            context.close()


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    answer = call_gpt(
        prompt="Hello! Introduce yourself briefly.",
        worker_id=1,
    )

    print(answer)