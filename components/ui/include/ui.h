#ifndef UI_H
#define UI_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Zero-part user interface: the SuperMini's own blue LED for feedback and its BOOT button as the
 * fallback lamp toggle, plus the optional carrier footprints (status LED D4, button SW1) if fitted.
 */

/** Call ui_button_pressed() at this interval; debouncing is counted in polls. */
#define UI_BUTTON_POLL_MS 10

/** @brief Configure the LED (off) and the buttons (inputs with pull-ups). */
esp_err_t ui_init(void);

/**
 * @brief Light the LED for @p on_ms, then turn it off. Non-blocking; a new flash restarts the timer.
 */
void ui_led_flash(uint32_t on_ms);

/**
 * @brief Poll the buttons; call every UI_BUTTON_POLL_MS from one task.
 * @return true exactly once per debounced press of either button.
 */
bool ui_button_pressed(void);

#ifdef __cplusplus
}
#endif

#endif /* UI_H */
