; Robot Initialization G-Code Configuration
; Sent upon connection by the Python script

; set StallGuard threshold values for sensorless homing
M914 X85 Y85 Z100 


; Steps per unit
M92 X80.00 Y80.00 Z400.00 E345.00

; Max feedrates (units/s)
M203 X8000.00 Y8000.00 Z1000.00 E25.00

; Max Acceleration (units/s^2)
M201 X500.00 Y500.00 Z100.00 E1000.00

; Acceleration (units/s^2) (P<print> R<retract> T<travel>)
M204 P500.00 R500.00 T1000.00

; Advanced (B<min_segment_time_us> S<min_feedrate> T<min_travel_feedrate> J<junction_deviation>)
M205 B20000.00 S0.00 T0.00 J0.01

; Home offset (mm)
M206 X0.00 Y0.00 Z0.00

; Stepper driver current (mA) - Use with caution!
M906 X1100 Y1100 Z750
M906 T0 E750 ; Assuming E is on T0



; Driver stepping mode (Example uses S1 = SpreadCycle for X Y Z E) - Check your board/drivers
M569 S1 X Y Z
M569 S1 T0 E


