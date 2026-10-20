#ifndef LAMP_H
#define LAMP_H

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Configure the lamp enable pin and switch the lamp off.
 *
 * The pin is driven low before it becomes an output, so the lamp cannot flash on during start-up.
 */
esp_err_t lamp_init(void);

/** @brief Switch the lamp on or off. Safe to call from any task. */
void lamp_set(bool on);

/** @brief Current lamp state as last commanded. */
bool lamp_is_on(void);

/**
 * @brief Flip the lamp state. Safe to call from any task.
 * @return The new state (true = on).
 */
bool lamp_toggle(void);

#ifdef __cplusplus
}
#endif

#endif /* LAMP_H */
