/*
 * adc_sampler: continuous ADC capture of the Azura microphone channel.
 *
 * Original design by Joe Gould (continuous mode + DMA on ADC1_CH0 at 16 kHz). Reworked against the
 * ESP-IDF v6.1 driver source:
 *  - the reader blocks in adc_continuous_read() instead of waiting on a queue token per frame. The
 *    driver's ISR fires on_conv_done even when its ring-buffer push failed, so token counts and
 *    frames drift apart after an overflow;
 *  - short reads are normal (the pool is a byte ring buffer and returns less at its wrap point), so
 *    every whole result that arrives is used;
 *  - results are decoded with adc_continuous_parse_data() and checked for channel and validity;
 *  - the pool holds 16 frames (128 ms), and flush_pool keeps the newest audio if the reader stalls.
 */
#include "adc_sampler.h"

#include <inttypes.h>
#include <string.h>

#include "esp_adc/adc_continuous.h"
#include "esp_attr.h"
#include "esp_check.h"
#include "esp_log.h"
#include "soc/soc_caps.h"

#define SAMPLER_UNIT        ADC_UNIT_1
#define SAMPLER_CHANNEL     ADC_CHANNEL_0   /* GPIO0 on the ESP32-C3 */
#define SAMPLER_ATTEN       ADC_ATTEN_DB_12 /* about 0-2.5 V on the ESP32-C3 */
#define SAMPLER_FRAME_BYTES (ADC_SAMPLER_FRAME_SAMPLES * SOC_ADC_DIGI_RESULT_BYTES)
#define SAMPLER_POOL_FRAMES 16
#define SAMPLER_POOL_BYTES  (SAMPLER_POOL_FRAMES * SAMPLER_FRAME_BYTES)

static const char *TAG = "adc_sampler";

static adc_continuous_handle_t s_handle;
static uint8_t s_raw[SAMPLER_FRAME_BYTES];
static adc_continuous_data_t s_parsed[ADC_SAMPLER_FRAME_SAMPLES];
static adc_sampler_stats_t s_stats;
static volatile uint32_t s_overflows; /* written from the driver ISR */

static bool IRAM_ATTR on_pool_ovf(adc_continuous_handle_t handle, const adc_continuous_evt_data_t *edata,
                                  void *user_data)
{
    (void)handle;
    (void)edata;
    (void)user_data;
    s_overflows++;
    return false; /* no task to wake */
}

esp_err_t adc_sampler_start(void)
{
    esp_err_t ret = ESP_OK;
    ESP_RETURN_ON_FALSE(s_handle == NULL, ESP_ERR_INVALID_STATE, TAG, "already started");

    const adc_continuous_handle_cfg_t handle_cfg = {
        .max_store_buf_size = SAMPLER_POOL_BYTES,
        .conv_frame_size = SAMPLER_FRAME_BYTES,
        .flags = {
            .flush_pool = 1,
        },
    };
    ESP_RETURN_ON_ERROR(adc_continuous_new_handle(&handle_cfg, &s_handle), TAG, "adc_continuous_new_handle");

    adc_digi_pattern_config_t pattern = {
        .atten = SAMPLER_ATTEN,
        .channel = SAMPLER_CHANNEL,
        .unit = SAMPLER_UNIT,
        .bit_width = SOC_ADC_DIGI_MAX_BITWIDTH,
    };
    const adc_continuous_config_t cfg = {
        .pattern_num = 1,
        .adc_pattern = &pattern,
        .sample_freq_hz = ADC_SAMPLER_SAMPLE_RATE_HZ,
        .conv_mode = ADC_CONV_SINGLE_UNIT_1,
    };
    ESP_GOTO_ON_ERROR(adc_continuous_config(s_handle, &cfg), fail, TAG, "adc_continuous_config");

    const adc_continuous_evt_cbs_t cbs = {
        .on_pool_ovf = on_pool_ovf,
    };
    ESP_GOTO_ON_ERROR(adc_continuous_register_event_callbacks(s_handle, &cbs, NULL), fail, TAG,
                      "adc_continuous_register_event_callbacks");

    memset(&s_stats, 0, sizeof(s_stats));
    s_overflows = 0;
    ESP_GOTO_ON_ERROR(adc_continuous_start(s_handle), fail, TAG, "adc_continuous_start");

    ESP_LOGI(TAG, "sampling GPIO0 at %d Hz, %d-sample frames, %d ms pool", ADC_SAMPLER_SAMPLE_RATE_HZ,
             ADC_SAMPLER_FRAME_SAMPLES, SAMPLER_POOL_FRAMES * ADC_SAMPLER_FRAME_SAMPLES * 1000 / ADC_SAMPLER_SAMPLE_RATE_HZ);
    return ESP_OK;

fail:
    adc_continuous_deinit(s_handle);
    s_handle = NULL;
    return ret;
}

size_t adc_sampler_read(uint16_t *out, size_t max_samples, TickType_t ticks_to_wait)
{
    if (s_handle == NULL || out == NULL || max_samples == 0) {
        return 0;
    }
    size_t want = max_samples < ADC_SAMPLER_FRAME_SAMPLES ? max_samples : ADC_SAMPLER_FRAME_SAMPLES;
    uint32_t timeout_ms = (ticks_to_wait == portMAX_DELAY) ? ADC_MAX_DELAY : (uint32_t)pdTICKS_TO_MS(ticks_to_wait);

    uint32_t got_bytes = 0;
    esp_err_t err = adc_continuous_read(s_handle, s_raw, want * SOC_ADC_DIGI_RESULT_BYTES, &got_bytes, timeout_ms);
    if (err == ESP_ERR_TIMEOUT) {
        return 0;
    }
    if (err != ESP_OK) {
        s_stats.read_errors++;
        return 0;
    }

    uint32_t parsed = 0;
    err = adc_continuous_parse_data(s_handle, s_raw, got_bytes, s_parsed, &parsed);
    if (err != ESP_OK) {
        s_stats.read_errors++;
        return 0;
    }

    size_t n = 0;
    for (uint32_t i = 0; i < parsed; i++) {
        const adc_continuous_data_t *d = &s_parsed[i];
        if (d->valid && d->unit == SAMPLER_UNIT && d->channel == SAMPLER_CHANNEL) {
            out[n++] = (uint16_t)d->raw_data;
        } else {
            s_stats.bad_results++;
        }
    }
    s_stats.samples += n;
    return n;
}

void adc_sampler_get_stats(adc_sampler_stats_t *out)
{
    if (out == NULL) {
        return;
    }
    *out = s_stats;
    out->overflows = s_overflows;
}

esp_err_t adc_sampler_stop(void)
{
    ESP_RETURN_ON_FALSE(s_handle != NULL, ESP_ERR_INVALID_STATE, TAG, "not started");
    ESP_RETURN_ON_ERROR(adc_continuous_stop(s_handle), TAG, "adc_continuous_stop");
    ESP_RETURN_ON_ERROR(adc_continuous_deinit(s_handle), TAG, "adc_continuous_deinit");
    s_handle = NULL;
    ESP_LOGI(TAG, "stopped after %" PRIu32 " samples, %" PRIu32 " overflows", s_stats.samples, (uint32_t)s_overflows);
    return ESP_OK;
}
