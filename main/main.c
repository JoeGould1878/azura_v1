/*
 * Azura v1, Phase 0 bring-up firmware ("hello-lamp").
 *
 * - The BOOT button (or the optional SW1) toggles the lamp through GPIO3 / SY6280 EN.
 * - The blue LED gives a short heartbeat every 2 s and a longer flash when the lamp changes.
 * - The ADC sampler runs at 16 kHz in its own task. Once a second the log reports the microphone
 *   channel's level, so the analogue chain can be checked on the bench before the clap detector
 *   (Phase 1b) is plugged into the same task.
 *
 * Works on a bare SuperMini too: GPIO0 just reads whatever it floats to.
 */
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>

#include "adc_sampler.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lamp.h"
#include "ui.h"

static const char *TAG = "azura";

#define AUDIO_TASK_PRIORITY   10
#define AUDIO_TASK_STACK      4096
#define HEARTBEAT_PERIOD_MS   2000
#define REPORT_PERIOD_MS      1000

/* Level statistics accumulated by the audio task and collected once a second by the main loop. */
typedef struct {
    uint32_t count;
    uint16_t min;
    uint16_t max;
    uint64_t sum;
    uint64_t sum_sq;
} level_stats_t;

static portMUX_TYPE s_level_lock = portMUX_INITIALIZER_UNLOCKED;
static level_stats_t s_level = {.min = UINT16_MAX};

static void audio_task(void *arg)
{
    (void)arg;
    static uint16_t samples[ADC_SAMPLER_FRAME_SAMPLES];

    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (;;) {
        size_t n = adc_sampler_read(samples, ADC_SAMPLER_FRAME_SAMPLES, pdMS_TO_TICKS(100));
        esp_task_wdt_reset();
        if (n == 0) {
            continue;
        }

        uint16_t lo = UINT16_MAX, hi = 0;
        uint32_t sum = 0;
        uint64_t sum_sq = 0;
        for (size_t i = 0; i < n; i++) {
            uint16_t s = samples[i];
            lo = s < lo ? s : lo;
            hi = s > hi ? s : hi;
            sum += s;
            sum_sq += (uint32_t)s * s;
        }

        taskENTER_CRITICAL(&s_level_lock);
        s_level.count += n;
        s_level.sum += sum;
        s_level.sum_sq += sum_sq;
        s_level.min = lo < s_level.min ? lo : s_level.min;
        s_level.max = hi > s_level.max ? hi : s_level.max;
        taskEXIT_CRITICAL(&s_level_lock);
    }
}

static uint32_t isqrt_u64(uint64_t v)
{
    uint64_t r = 0;
    uint64_t bit = 1ULL << 62;
    while (bit > v) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (v >= r + bit) {
            v -= r + bit;
            r = (r >> 1) + bit;
        } else {
            r >>= 1;
        }
        bit >>= 2;
    }
    return (uint32_t)r;
}

static void report_level(void)
{
    level_stats_t snap;
    taskENTER_CRITICAL(&s_level_lock);
    snap = s_level;
    s_level = (level_stats_t){.min = UINT16_MAX};
    taskEXIT_CRITICAL(&s_level_lock);

    adc_sampler_stats_t st;
    adc_sampler_get_stats(&st);

    if (snap.count == 0) {
        ESP_LOGW(TAG, "no ADC samples in the last second (read errors %" PRIu32 ")", st.read_errors);
        return;
    }
    /* Integer maths only: the C3 has no FPU and this keeps float printf out of the build. */
    uint32_t mean = (uint32_t)(snap.sum / snap.count);
    uint64_t mean_sq_x100 = (snap.sum_sq * 100) / snap.count; /* E[x^2] * 100 */
    uint64_t sq_mean_x100 = (snap.sum * snap.sum * 100) / ((uint64_t)snap.count * snap.count);
    uint64_t var_x100 = mean_sq_x100 > sq_mean_x100 ? mean_sq_x100 - sq_mean_x100 : 0;
    uint32_t rms_x10 = isqrt_u64(var_x100);
    ESP_LOGI(TAG, "adc: %" PRIu32 " samples/s, mean %" PRIu32 ", ac rms %" PRIu32 ".%" PRIu32 ", min %u, max %u"
                  " | overflows %" PRIu32 ", bad %" PRIu32 ", errors %" PRIu32,
             snap.count, mean, rms_x10 / 10, rms_x10 % 10, (unsigned)snap.min, (unsigned)snap.max, st.overflows,
             st.bad_results, st.read_errors);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Azura v1 bring-up firmware %s", esp_app_get_description()->version);

    ESP_ERROR_CHECK(lamp_init());
    ESP_ERROR_CHECK(ui_init());
    ESP_ERROR_CHECK(adc_sampler_start());
    xTaskCreate(audio_task, "audio", AUDIO_TASK_STACK, NULL, AUDIO_TASK_PRIORITY, NULL);

    ESP_LOGI(TAG, "press BOOT to toggle the lamp");

    TickType_t last_heartbeat = xTaskGetTickCount();
    TickType_t last_report = last_heartbeat;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(UI_BUTTON_POLL_MS));

        if (ui_button_pressed()) {
            bool on = lamp_toggle();
            ui_led_flash(on ? 400 : 150);
        }

        TickType_t now = xTaskGetTickCount();
        if (now - last_heartbeat >= pdMS_TO_TICKS(HEARTBEAT_PERIOD_MS)) {
            last_heartbeat = now;
            ui_led_flash(20);
        }
        if (now - last_report >= pdMS_TO_TICKS(REPORT_PERIOD_MS)) {
            last_report = now;
            report_level();
        }
    }
}
