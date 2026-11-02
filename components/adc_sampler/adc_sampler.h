#ifndef ADC_SAMPLER_H
#define ADC_SAMPLER_H

#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Continuous capture of the microphone channel (ADC1 channel 0, GPIO0) with DMA.
 *
 * The ADC runs at ADC_SAMPLER_SAMPLE_RATE_HZ and the driver delivers frames of
 * ADC_SAMPLER_FRAME_SAMPLES results (each result is 4 bytes on the ESP32-C3). The driver keeps a
 * pool of frames so the reader can be late by up to ~128 ms; if it falls further behind, the oldest
 * audio is dropped and counted in adc_sampler_stats_t.overflows.
 *
 * Use from a single reader task: adc_sampler_start(), then adc_sampler_read() in a loop.
 */

/** Microphone sample rate. */
#define ADC_SAMPLER_SAMPLE_RATE_HZ 16000

/** Samples per DMA frame: 128 samples = 8 ms at 16 kHz. */
#define ADC_SAMPLER_FRAME_SAMPLES 128

/** Largest raw code the 12-bit ADC returns. */
#define ADC_SAMPLER_MAX_CODE 4095

typedef struct {
    uint32_t samples;     /*!< valid samples delivered to the caller */
    uint32_t overflows;   /*!< times the driver's pool filled up and audio was dropped */
    uint32_t bad_results; /*!< results flagged invalid or from an unexpected channel */
    uint32_t read_errors; /*!< failed reads or parses */
} adc_sampler_stats_t;

/**
 * @brief Create the continuous ADC driver and start sampling.
 * @return ESP_OK, ESP_ERR_INVALID_STATE if already started, or the driver's error code.
 */
esp_err_t adc_sampler_start(void);

/**
 * @brief Read raw 12-bit codes (0..ADC_SAMPLER_MAX_CODE) in arrival order.
 *
 * Blocks up to @p ticks_to_wait for data and returns at most @p max_samples (and at most one
 * frame) per call. A short count is normal; just call again.
 *
 * @return Number of samples written to @p out (0 on timeout or error).
 */
size_t adc_sampler_read(uint16_t *out, size_t max_samples, TickType_t ticks_to_wait);

/** @brief Copy the running counters. */
void adc_sampler_get_stats(adc_sampler_stats_t *out);

/** @brief Stop sampling and free the driver. */
esp_err_t adc_sampler_stop(void);

#ifdef __cplusplus
}
#endif

#endif /* ADC_SAMPLER_H */
