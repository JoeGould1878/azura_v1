#ifndef ADC_SAMPLER_H
#define ADC_SAMPLER_H

#include <stdint.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

/* 
 * ADC Configuration Macros
 * Frame size must be a multiple of the SOC ADC data size (4 bytes).
 * 256 bytes @ 16kHz 12-bit = 128 samples per frame (8ms ISR interval).
 */
#define ADC_SAMPLE_FREQ_HZ    16000
#define ADC_CONV_FRAME_SIZE   256
#define ADC_STORE_BUF_SIZE    1024

/**
 * @brief Initialises the continuous ADC DMA engine.
 * 
 * @param dsp_queue FreeRTOS Queue handle used to pass DMA buffer pointers 
 *                  from the hardware ISR to the DSP task.
 * @return esp_err_t ESP_OK on success, ESP_ERR_NO_MEM if allocation fails, 
 *                   or ESP_ERR_INVALID_ARG for bad parameters.
 */
esp_err_t adc_sampler_init(QueueHandle_t dsp_queue_handle);

/**
 * @brief Blocks the calling task until a new audio frame is ready.
 * 
 * @param out_buffer Pointer to a local buffer (minimum ADC_CONV_FRAME_SIZE bytes) 
 *                   where the DMA data will be copied for DSP processing.
 * @param ticks_to_wait FreeRTOS ticks to wait before timing out.
 * @return esp_err_t ESP_OK if data was received, ESP_ERR_TIMEOUT if the queue timed out.
 */
esp_err_t adc_sampler_wait_for_data(uint8_t *out_buffer, TickType_t ticks_to_wait);

/**
 * @brief Safely halts the ADC DMA engine, deregisters the ISR, and frees memory.
 * 
 * @return esp_err_t ESP_OK on success, or applicable hardware error codes.
 */
esp_err_t adc_sampler_deinit(void);
/**
 * @brief Retrieves the number of ADC DMA buffer overflow events since initialization.
 * Getter to expose static overflow_counter to the DSP task for monitoring purposes.
 * @return uint32_t The count of overflow events.
 */
uint32_t adc_sampler_get_overflow_count(void);
#endif /* ADC_SAMPLER_H */