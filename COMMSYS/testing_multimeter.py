import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
for pin in (8,11,10,9):  # NSS=SCE0=8, SCLK=11, MOSI=10, MISO=9
    GPIO.setup(pin, GPIO.OUT if pin!=9 else GPIO.IN, pull_up_down=GPIO.PUD_OFF)
GPIO.output(8,1); GPIO.output(11,1); GPIO.output(10,1)
time.sleep(60)  # measure with a multimeter now
