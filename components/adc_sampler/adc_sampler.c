#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_adc/adc_continuous.h"
#include "freertos/queue.h"
#define ADC_SAMPLE_FREQ_HZ    16000
#define ADC_CONV_FRAME_SIZE   256
#define ADC_STORE_BUF_SIZE    1024
#define ADC_CHAN ADC_CHANNEL_0 //Gpio 36 on esp32, GPIO 0 on esp32c3 (CHAN_0 UNIT_1)
const char *TAG = "adc_sampler";
//declare handle for the ADC continuous driver outside init so it is not deleted on return
adc_continuous_handle_t adc_handle = NULL;
//declare static queue handle to be used in the ISR callbacks and wait_for_data() function populated by param of adc_sampler_init()
static QueueHandle_t dsp_queue_handle_static = NULL;
//declare overflow counter to track number of times the ADC DMA buffer has overflowed
static volatile uint32_t overflow_counter = 0; 
//Helper to expose overflow counter to DSP task
uint32_t adc_sampler_get_overflow_count(void) {
    return overflow_counter;
}
static bool IRAM_ATTR adc_sampler_on_conv_done(adc_continuous_handle_t handle, const adc_continuous_evt_data_t *edata, void *user_data);
static bool IRAM_ATTR adc_sampler_on_pool_ovf(adc_continuous_handle_t handle, const adc_continuous_evt_data_t *edata, void *user_data);
/**
 * @brief Initialize and start the continuous ADC sampler.
 *
 * This function validates the DSP queue handle, creates a continuous ADC driver
 * instance, configures a single-channel ADC pattern for the selected ADC unit,
 * registers the conversion and overflow callbacks, and starts continuous sampling.
 *
 * The ADC is configured for a fixed sampling rate of 16 kHz using a single input
 * pattern on ADC unit 1, with the callback ISR signaling the DSP task whenever a
 * conversion completes so the DSP task can read the captured samples from the DMA
 * buffer in normal task context.
 *
 * @param[in] dsp_queue_handle Handle to the FreeRTOS queue used to notify the DSP
 *                            task when new ADC samples are available.
 *
 * @return ESP_OK if the ADC sampler was initialized and started successfully;
 *         otherwise, an ESP error code describing the failure.
 */
esp_err_t adc_sampler_init(QueueHandle_t dsp_queue_handle){
    esp_err_t err = ESP_OK;
    if (dsp_queue_handle==NULL) {
        err = ESP_ERR_INVALID_ARG;
        ESP_LOGE(TAG, "_init() FAILED on invalid argument, queue undefined: %s", esp_err_to_name(err));
        return err;
    }
    //Save queue handle statically for use in the ISR callbacks & wait_for_data() function
    dsp_queue_handle_static = dsp_queue_handle;
//declare the adc_cfg struct for the ADC continuous driver
    adc_continuous_handle_cfg_t adc_handle_cfg = {
        .max_store_buf_size = ADC_STORE_BUF_SIZE,
        .conv_frame_size = ADC_CONV_FRAME_SIZE,
    };
    err = adc_continuous_new_handle(&adc_handle_cfg, &adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_init() FAILED to create ADC handle: %s", esp_err_to_name(err));
        return err;
    }
    //populate adc_digi_pattern_config struct with attenuation and bit width settings, this is then a element in the adc_config struct
    adc_digi_pattern_config_t adc_pattern = {
        .atten = ADC_ATTEN_DB_12,
        .bit_width = ADC_BITWIDTH_DEFAULT,
        .channel = ADC_CHAN,
        .unit = ADC_UNIT_1,
    };
   //populate adc_config struct with the pattern and sample frequency
    adc_continuous_config_t adc_config = {
        .sample_freq_hz = ADC_SAMPLE_FREQ_HZ,
        .conv_mode = ADC_CONV_SINGLE_UNIT_1,
        #ifdef CONFIG_IDF_TARGET_ESP32    
            .format = ADC_DIGI_OUTPUT_FORMAT_TYPE1,
        #else 
            .format = ADC_DIGI_OUTPUT_FORMAT_TYPE2,
        #endif
        .pattern_num = 1,
        .adc_pattern = &adc_pattern,
    };

    err = adc_continuous_config(adc_handle, &adc_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_init() FAILED to configure ADC: %s", esp_err_to_name(err));
        return err;
    }
    //populate the callback struct with the ISR functions
    adc_continuous_evt_cbs_t cbs = {
        .on_conv_done = adc_sampler_on_conv_done,
        .on_pool_ovf = adc_sampler_on_pool_ovf
    };
    err = adc_continuous_register_event_callbacks(adc_handle, &cbs, dsp_queue_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_init() FAILED to register event callbacks: %s", esp_err_to_name(err));
        return err;
    }
    //Start the ADC continuous sampling
    err = adc_continuous_start(adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_init() FAILED to start ADC: %s", esp_err_to_name(err));
        return err;
    }
    return(err);
}
/**
 * ISR Callback function for ADC conversion done event
 * Calles in ISR context when ADC DMA engine has filled a 256 byte buffer with 128 samples of 12bit audio data
 * ISR sends simple bool true flag to DSP task to indicate new data is availale,
 *DSP task will then read the data from the ADC DMA buffer in normal task context using adc_continuous_read() to avoid doing any heavy processing in the ISR context
 */
static bool IRAM_ATTR adc_sampler_on_conv_done(adc_continuous_handle_t handle, const adc_continuous_evt_data_t *edata, void *user_data) {
    QueueHandle_t dsp_queue_handle = (QueueHandle_t)user_data;
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    if (dsp_queue_handle != NULL) {
        bool new_data_available = true;
        xQueueSendFromISR(dsp_queue_handle, &new_data_available, &xHigherPriorityTaskWoken);
    }
    return(xHigherPriorityTaskWoken == pdTRUE); 
    // Return true to force context switch to DSP task which will read process new data or false if handle was null as we have no queue to push to
}

/** 
 * ISR Callback function for ADC DMA buffer overflow event
 * Called in ISR context when the ADC DMA buffer overflows
 * Increments the overflow counter and returns false to indicate that no context switch is needed, as the DSP task will handle the overflow in normal task context
 */
static bool IRAM_ATTR adc_sampler_on_pool_ovf(adc_continuous_handle_t handle, const adc_continuous_evt_data_t *edata, void *user_data) {
    overflow_counter++;
    return false; // Return false to indicate that the event was not handled and no context switch is needed
}
/**@brief Waits for new ADC data to be available
 * @param out_buffer Pointer to the buffer where the ADC data will be stored
 * @param ticks_to_wait Number of ticks to wait for new data
 * @return ESP_OK if data is available, otherwise an error code
 */
esp_err_t adc_sampler_wait_for_data(uint8_t *out_buffer, TickType_t ticks_to_wait){
    esp_err_t err = ESP_OK;
    if (out_buffer==NULL) {
        err = ESP_ERR_INVALID_ARG;
        ESP_LOGE(TAG, "_wait_for_data() FAILED on invalid argument, out_buffer undefined: %s", esp_err_to_name(err));
        return err; 
    }
    // Wait for the DSP task to receive a notification from the ADC ISR that new data is available
    bool new_data_available = false;
    if(xQueueReceive(dsp_queue_handle_static, &new_data_available, ticks_to_wait) != pdTRUE) {
        err = ESP_ERR_TIMEOUT;
        ESP_LOGE(TAG, "_wait_for_data() FAILED on timeout on receive from queue, waited %u ms: %s", (uint32_t)pdTICKS_TO_MS(ticks_to_wait), esp_err_to_name(err));
        return err;
    }
    // Read the ADC DMA buffer into the provided out_buffer
    uint32_t bytes_read = 0;
    err = adc_continuous_read(adc_handle, out_buffer, ADC_CONV_FRAME_SIZE, &bytes_read, (uint32_t)pdTICKS_TO_MS(ticks_to_wait));
    if(err==ESP_ERR_TIMEOUT){
        ESP_LOGE(TAG, "_wait_for_data() FAILED on timeout on ADC read, waited %u ms: %s", (uint32_t)pdTICKS_TO_MS(ticks_to_wait), esp_err_to_name(err));
        return(err);
    }
    if(err==ESP_ERR_INVALID_STATE){
        ESP_LOGE(TAG, "_wait_for_data() failed on invalid driver state, ADC sampling rate may be faster than task processing rate: %s", esp_err_to_name(err));
        return(err);
    }
    if(bytes_read<ADC_CONV_FRAME_SIZE){
        err = ESP_FAIL;
        ESP_LOGE(TAG, "_wait_for_data() FAILED read incomplete ADC frame: %s", esp_err_to_name(err));
        return(err);
    }
    return err;
}

esp_err_t adc_sampler_deinit(void){
     esp_err_t err = ESP_OK;
    if(adc_handle==NULL){
        err = ESP_ERR_INVALID_STATE;
        ESP_LOGE(TAG, "_deinit() FAILED on invalid state, there is no active ADC handle to deinitialise: %s", esp_err_to_name(err));
        return err;
    }
    //Stop the ADC continuous sampling
    err = adc_continuous_stop(adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_deinit() FAILED to stop ADC: %s", esp_err_to_name(err));
        return err;
    }
    //Deregister the event callbacks
    err = adc_continuous_register_event_callbacks(adc_handle, NULL, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_deinit() FAILED to deregister event callbacks: %s", esp_err_to_name(err));
        return err;
    }
    //Delete the ADC continuous driver handle
    err = adc_continuous_del_handle(adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "_deinit() FAILED to delete ADC handle: %s", esp_err_to_name(err));
        return err;
    }
    //Reset the static queue handle to NULL to avoid dangling pointer
    dsp_queue_handle_static = NULL;
    ESP_LOGI(TAG, "_deinit() SUCCESS: %s", esp_err_to_name(err));
    return err;
    
}
