#include "lamp.h"

#include "board.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "lamp";

/* The detector (audio task) and the button (main task) can both switch the lamp. */
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static bool s_on;

esp_err_t lamp_init(void)
{
    /* Set the output latch low first, then enable the output driver. */
    gpio_set_level(BOARD_GPIO_LAMP_EN, 0);
    const gpio_config_t io = {
        .pin_bit_mask = 1ULL << BOARD_GPIO_LAMP_EN,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE, /* R10 on the board does this job */
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&io);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "gpio_config failed: %s", esp_err_to_name(err));
        return err;
    }
    gpio_set_level(BOARD_GPIO_LAMP_EN, 0);
    s_on = false;
    ESP_LOGI(TAG, "ready on GPIO%d, lamp off", BOARD_GPIO_LAMP_EN);
    return ESP_OK;
}

void lamp_set(bool on)
{
    bool changed;
    taskENTER_CRITICAL(&s_lock);
    changed = (on != s_on);
    s_on = on;
    gpio_set_level(BOARD_GPIO_LAMP_EN, on ? 1 : 0);
    taskEXIT_CRITICAL(&s_lock);
    if (changed) {
        ESP_LOGI(TAG, "lamp %s", on ? "ON" : "OFF");
    }
}

bool lamp_is_on(void)
{
    return s_on;
}

bool lamp_toggle(void)
{
    bool on;
    taskENTER_CRITICAL(&s_lock);
    on = !s_on;
    s_on = on;
    gpio_set_level(BOARD_GPIO_LAMP_EN, on ? 1 : 0);
    taskEXIT_CRITICAL(&s_lock);
    ESP_LOGI(TAG, "lamp %s", on ? "ON" : "OFF");
    return on;
}
