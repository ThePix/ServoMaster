This software is designed to run on a Raspberry Pi, communicationg with devices across an I2C bus. Its purpose is to control points and other devices on a model railway, using servos.

Servos are to be connected to several PCA 9685 boards. Part of the purpose is to provide a smooth and slow movement for the servos, which can be configured on a point-bypoint basis. Servo angles can be modified via the GUI and the values saved to file.

It will respond to physical push buttons to change points and will change LEDs to show the state of points, both connected to PCF8575 boards. These will be configured in a simple text file.

The software includes a GUI. This should be used for configuring and diagnostics. During normal operations it is assumed no monitor, mouse or keyboard are connected.

This replaces a previous project using an Arduino (see [here](https://github.com/ThePix/Arduino_i2c)).
