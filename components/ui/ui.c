#include "ui.h"

#include "board.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "ui";

/* A press must read the same for this many consecutive polls (30 ms) to count. */
#define DEBOUNCE_POLLS 3

static esp_timer_handle_t s_led_timer;
static uint8_t s_stable_count;
static bool s_pressed;

static void led_write(bool on)
{
    gpio_set_level(BOARD_GPIO_LED, on ? BOARD_LED_ACTIVE_LEVEL : !BOARD_LED_ACTIVE_LEVEL);
    gpio_set_level(BOARD_GPIO_EXT_LED, on ? BOARD_EXT_LED_ACTIVE_LEVEL : !BOARD_EXT_LED_ACTIVE_LEVEL);
}

static void led_off_cb(void *arg)
{
    (void)arg;
    led_write(false);
}

esp_err_t ui_init(void)
{
    led_write(false);
    const gpio_config_t led = {
        .pin_bit_mask = (1ULL << BOARD_GPIO_LED) | (1ULL << BOARD_GPIO_EXT_LED),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&led);
    if (err != ESP_OK) {
        return err;
    }
    led_write(false);

    const gpio_config_t buttons = {
        .pin_bit_mask = (1ULL << BOARD_GPIO_BOOT_BUTTON) | (1ULL << BOARD_GPIO_EXT_BUTTON),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, /* SW1 is optional: an empty footprint just reads high */
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    err = gpio_config(&buttons);
    if (err != ESP_OK) {
        return err;
    }

    const esp_timer_create_args_t timer_args = {
        .callback = led_off_cb,
        .name = "led_off",
    };
    err = esp_timer_create(&timer_args, &s_led_timer);
    if (err != ESP_OK) {
        return err;
    }
    ESP_LOGI(TAG, "LEDs on GPIO%d (module) and GPIO%d (D4), buttons on GPIO%d (BOOT) and GPIO%d (SW1)",
             BOARD_GPIO_LED, BOARD_GPIO_EXT_LED, BOARD_GPIO_BOOT_BUTTON, BOARD_GPIO_EXT_BUTTON);
    return ESP_OK;
}

void ui_led_flash(uint32_t on_ms)
{
    if (s_led_timer == NULL) {
        return;
    }
    esp_timer_stop(s_led_timer); /* ignore "not running" */
    led_write(true);
    esp_timer_start_once(s_led_timer, (uint64_t)on_ms * 1000);
}

bool ui_button_pressed(void)
{
    bool down = gpio_get_level(BOARD_GPIO_BOOT_BUTTON) == 0 || gpio_get_level(BOARD_GPIO_EXT_BUTTON) == 0;

    if (down == s_pressed) {
        s_stable_count = 0;
        return false;
    }
    if (++s_stable_count < DEBOUNCE_POLLS) {
        return false;
    }
    s_stable_count = 0;
    s_pressed = down;
    return down; /* report the press edge only */
}
