#ifndef BOARD_H
#define BOARD_H

/*
 * Azura v1 pin map: the one place GPIO numbers live.
 *
 * Module: ESP32-C3 SuperMini on sockets J2/J3. J3 is the 5V / GND / 3V3 / GPIO4..GPIO0 row.
 * Check these against the silkscreen of the module you actually use; clones vary.
 */

/* Microphone channel (op-amp output through R8/C9). ADC1 channel 0 is GPIO0 on the C3. */
#define BOARD_GPIO_ADC          0

/* SY6280 EN: high = lamp on. R10 pulls it low through reset, so the lamp is off at boot. */
#define BOARD_GPIO_LAMP_EN      3

/* The module's own blue LED, wired active low. */
#define BOARD_GPIO_LED          8
#define BOARD_LED_ACTIVE_LEVEL  0

/* Optional status LED on the carrier (unfitted footprints D4 + R21 on J2, GPIO7 -> R21 -> D4 -> GND),
 * active high. Driven together with the module LED; harmless when not fitted. */
#define BOARD_GPIO_EXT_LED          7
#define BOARD_EXT_LED_ACTIVE_LEVEL  1

/* The module's BOOT button, active low. Holding it at reset enters the bootloader;
 * after boot it is a free input and serves as the manual (fallback) lamp toggle. */
#define BOARD_GPIO_BOOT_BUTTON  9

/* Optional external tact switch (unfitted footprint SW1 on J2), active low, internal pull-up. */
#define BOARD_GPIO_EXT_BUTTON   10

#endif /* BOARD_H */
