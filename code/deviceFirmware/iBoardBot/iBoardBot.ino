// iBoardBot PROJECT
// Author: Jose Julio & Juan pedro (JJROBOTS)
// Hardware: Arduino Leonardo + JJROBOTS BROBOT shield 2 (new) with ESP-12E Wifi module
// ESP8266 firmware version 1.0.1 or higher
// Date: 18/04/2015
// Last updated: 19/02/2017
// Version: 1.08
// Project page : http://jjrobots.com/
// Kickstarter page:https://www.kickstarter.com/projects/879074320/iboardbot-the-internet-controlled-whiteboard-robot
// GIT repository: https://github.com/jjrobots/iBoardbot
// License: Open Software GPL License v2

// Hardware:
// X Motor (longitudinal move) connected to MOTOR2 output
// Y Motor (vertical move) connected to MOTOR1 output
// Eraser servo connected to Servo1 output
// PEN Lift servo connected to Servo2 output

#include <EEPROM.h>
#include <avr/pgmspace.h>

#define VERSION "iBoardBot 1.08"
#define DEBUG 2

// ROBOT and USER configuration parameters
#include "Configuration.h"

unsigned char buffer[780];   // buffer to store incomming message from server
bool draw_task = false;
bool new_packet = false;
int block_number;
bool next_block = false;
char MAC[13];  // MAC address of Wifi module


// Configuration: Pins, servos, Steppers, Wifi...
void setup()
{
  // STEPPER PINS ON JJROBOTS BROBOT BRAIN BOARD
  pinMode(4, OUTPUT); // ENABLE MOTORS
  pinMode(7, OUTPUT); // STEP MOTOR 1 PORTE,6
  pinMode(8, OUTPUT); // DIR MOTOR 1  PORTB,4
  pinMode(12, OUTPUT); // STEP MOTOR 2 PORTD,6
  pinMode(5, OUTPUT); // DIR MOTOR 2  PORTC,6
  pinMode(A0, INPUT); // WIFI CONFIG BUTTON => sensor imput
  pinMode(13, OUTPUT); // Servo pin
  digitalWrite(A0, HIGH); // Enable Pullup on A0
  digitalWrite(4, HIGH);  // Disbale motors

  pinMode(10, OUTPUT);  // Servo1
  pinMode(6, OUTPUT);   // Servo2
  pinMode(2, OUTPUT);   // SERVOs aux (on I2C)

  delay(100);
  Serial.begin(115200); // Serial output to console
  //while (!Serial);      // Arduino Leonardo wait for Serial port to open...

  Serial1.begin(115200); // Wifi initialization

  delay(1000);

  // Manual Configuration mode? => Erase stored Wifi parameters (force A0 to ground)
  if (digitalRead(A0) == LOW) {
    writeWifiConfig(0, "", "", "", 0);
  }
  
#ifdef DEBUG
  delay(10000);  // Only needed for serial debug
  Serial.println(VERSION);
#endif

  // Init servos
  Serial.println(F("Servo init..."));
  servo_pos1 = SERVO1_ERASER;
  servo_pos2 = SERVO2_PAINT;
  initServo();
  moveServo1(SERVO1_ERASER);
  moveServo2(SERVO2_PAINT);
  delay(1000);
  disableServo1();
  disableServo2();

  Serial.println(F("Reading Wifi configuration..."));
  readWifiConfig();

  Serial.print( F("WifiConfig.status: "));
  Serial.println(WifiConfig.status);
  Serial.print( F("WifiConfig.ssid: "));
  Serial.println(WifiConfig.ssid);
  Serial.print( F("WifiConfig.pass: "));
  Serial.println(WifiConfig.pass);
  Serial.print( F("WifiConfig.proxy: "));
  Serial.println(WifiConfig.proxy);
  Serial.print( F("WifiConfig.port: "));
  Serial.println(WifiConfig.port);

  // if wifi parameters are not configured we start the config web server
  if (WifiConfig.status != 1) {
    WifiConfigurationMode();
  }

  Wconnected = false;
  Network_errors = 0;
  while (!Wconnected) {
    // Wifi initialization
    Serial1.println();
    ESPflush();
    Serial1.println(F("AT+RST"));
    ESPwaitFor("ready", 10);
    Serial1.println(F("AT+GMR"));
    ESPwaitFor("OK", 5);
    GetMac();

    if (WifiConnect()) {
      digitalWrite(13, HIGH);
      Wconnected = true;
    }
    else {
      Serial.println(F("Error connecting to network!"));
      digitalWrite(13, LOW);
      delay(2500);
      Wconnected = false;
      Network_errors++;
      // If connection fail 2 times we enter WifiConfigurationMode
      if (Network_errors >= 2) {
        WifiConfigurationMode();
        Network_errors = 0;
      }
    }
  }

  // Configure TCP client (for HTTP connection to server)
  delay(250);
  Serial1.println(F("AT+CIFSR"));
  ESPwaitFor("OK", 3);
  Serial1.println(F("AT+CIPMUX=0"));
  ESPwaitFor("OK", 3);
  Serial1.println(F("AT+CIPMODE=0"));
  ESPwaitFor("OK", 3);
  Network_errors = 0;
  delay(200);

  //Initializing init position
  position_x = ROBOT_INITIAL_POSITION_X * X_AXIS_STEPS_PER_UNIT;
  position_y = ROBOT_INITIAL_POSITION_Y * Y_AXIS_STEPS_PER_UNIT;

  // Output parameters
  //Serial.print(F("Max_acceleration_x: "));
  //Serial.println(acceleration_x);
  //Serial.print(F("Max_acceleration_y: "));
  //Serial.println(acceleration_y);
  //Serial.print(F("Max speed X: "));
  //Serial.println(MAX_SPEED_X);
  //Serial.print(F("Max speed Y: "));
  //Serial.println(MAX_SPEED_Y);

  Serial.print(F("Free RAM: "));
  Serial.println(freeRam());

  // STEPPER MOTORS INITIALIZATION
  Serial.println(F("Steper motors initialization..."));
  // MOTOR1 = X axis => TIMER1
  TCCR1A = 0;                       // Timer1 CTC mode 4, OCxA,B outputs disconnected
  TCCR1B = (1 << WGM12) | (1 << CS11); // Prescaler=8, => 2Mhz
  OCR1A = MINIMUN_SPEED;               // Motor stopped
  dir_x = 0;
  TCNT1 = 0;

  // MOTOR2 = Y axis => TIMER3
  TCCR3A = 0;                       // Timer3 CTC mode 4, OCxA,B outputs disconnected
  TCCR3B = (1 << WGM32) | (1 << CS31); // Prescaler=8, => 2Mhz
  OCR3A = MINIMUN_SPEED;   // Motor stopped
  dir_y = 0;
  TCNT3 = 0;

  delay(200);
  //Serial.println("Moving to initial position...");
  // Initializing Robot command variables
  com_speed_x = MAX_SPEED_X / 2;
  com_speed_y = MAX_SPEED_Y / 2;
  max_speed_x = com_speed_x;
  max_speed_y = com_speed_y;

  //Initializing init position
  position_x = ROBOT_INITIAL_POSITION_X * X_AXIS_STEPS_PER_UNIT;
  position_y = ROBOT_INITIAL_POSITION_Y * Y_AXIS_STEPS_PER_UNIT;
  //last_position_x = position_x;
  //last_position_y = position_y;

  setSpeedS(com_speed_x, com_speed_y);
  setPosition_mm10(ROBOT_MIN_X * 10, ROBOT_MIN_Y * 10);
  last_move_x = ROBOT_INITIAL_POSITION_X * 10;
  last_move_y = ROBOT_INITIAL_POSITION_Y * 10;
  home_position = true;
  delay(50);

  // Enable TIMERs interrupts
  TIMSK1 |= (1 << OCIE1A); // Enable Timer1 interrupt
  TIMSK3 |= (1 << OCIE1A); // Enable Timer1 interrupt

  delay(50);

  ESPflush();

  Serial.println(F("Wifi parameters:"));
  Serial.print(F("Url:"));
  Serial.println(SERVER_URL);
  if ((WifiConfig.port > 0) && (WifiConfig.port < 65000) && (strlen(WifiConfig.proxy) > 0))
  {
    Serial.println(F("proxy : "));
    Serial.println(WifiConfig.proxy);
    Serial.println(F("port : "));
    Serial.println(WifiConfig.port);
  }
  Serial.println();
  Serial.println(VERSION);
  //Serial.print("ID_IWBB ");
  Serial.println(MAC);
  Serial.println(" Ready...");
  timer_old = micros();
  timeout_counter = 0;
  block_number = -1;
  commands_index = 0;
  commands_lines = 0;
  draw_task = false;

  // Ready signal
  enableServo1();
  enableServo2();

  // A bit more obvious
  moveServo2(SERVO2_LIFT);
  delay(600);
  moveServo2(SERVO2_PAINT);
  delay(600);
  moveServo2(SERVO2_LIFT);
  delay(600);
  moveServo2(SERVO2_PAINT);
  delay(2000);
  if (Wconnected) {
    moveServo2(SERVO2_LIFT);
    delay(1000);
    moveServo2(SERVO2_PAINT);
    delay(1000);
  }

  disableServo1();
  disableServo2();
}


void loop()
{
  uint8_t response;
  char get_string[110];
  int code1;
  int code2;

  debug_counter++;
  timer_value = micros();
  dt = timer_value - timer_old;
  if (dt >= 1000) { // 1Khz loop
    timer_old = timer_value;
    loop_counter++;
    if (draw_task) {
      adjustSpeed();
      positionControl(dt);   // position, speed and acceleration control of stepper motors
      timeout_counter++;
      wait_counter = 0;
      if ((timeout_counter > 8000) || ((myAbsLong(target_position_x - position_x) < POSITION_TOLERANCE_X) && (myAbsLong(target_position_y - position_y) < POSITION_TOLERANCE_Y))) { // Move done?
#if DEBUG==3
        Serial.print( F("made it; targetX: "));
        Serial.print( target_position_x );
        Serial.print( F(", position_x: "));
        Serial.print( position_x );
        Serial.print( F(", targetY: "));
        Serial.print( target_position_y );
        Serial.print( F(", position_y: "));
        Serial.println( position_y );
#endif
        if (timeout_counter > 8000) {
          Serial.print(F("!TimeoutCounter! ")); // 8 seconds timeout
          show_command = true;
          // Reset position on timeout?
        }
#if DEBUG==3
        if (show_command) {
          Serial.print( F("show move - position; x: "));
          Serial.print(position_x);
          Serial.print( F(", y:"));
          Serial.println(position_y);
        }
#endif
        if (commands_index < commands_lines) {
          // Reading bytes from Packet (3 bytes per command)
          int byte1 = buffer[commands_index * 3];
          int byte2 = buffer[commands_index * 3 + 1];
          int byte3 = buffer[commands_index * 3 + 2];
          // Decode the command (code1 and code2) each code is 12 bits
          code1 = (byte1 << 4) | ((byte2 & 0xF0) >> 4);
          code2 = ((byte2 & 0x0F) << 8) | (byte3);

#ifdef DEBUG
          if (show_command) {
            Serial.print( F("consuming command; commands_index: "));
            Serial.print(commands_index);
            Serial.print( F(", code1: "));
            Serial.print(code1);
            Serial.print( F(", code2: "));
            Serial.println(code2);
            show_command = false;
          }
#endif
          // DECODE protocol codes
          if ((new_packet) && (code1 != 4009)) { // check new packet
            // PACKET ERROR: No valid first command!
            Serial.print(F(" !PACKET ERROR!"));
            commands_index = 0;
            draw_task = false;
            disableServo1();
            disableServo2();
            servo_counter = 0;
            dir_x = 0;
            dir_y = 0;
          }
          else if (code1 == 4009) {
            new_packet = false;
            block_number = code2;
            if (block_number >= 4000) {
              block_number = -1;
            }
            Serial.print(F("Start block: "));
            Serial.println(block_number);
            show_command = true;
            servo_counter = 0;
            if (timeout_recover) {   // Timeout recovery mode? This means we had a timeout
              Serial.print(F("->Timeout recover!"));
              // Rewrite a PEN LIFT COMMAND 4003 0
              buffer[commands_index * 3] = (4003 >> 4);
              buffer[commands_index * 3+1]= ((4003 << 4) & 0xF0);
              buffer[commands_index * 3+2]= 0;
              timeout_recover = false;
            } else {
              commands_index++;
            }
          }
          else if ((code1 == 4001) && (code2 == 4001)) { // START DRAWING
            if (servo_counter == 0) {
              Serial.println(F(" !START DRAW"));
              enableServo1();
              enableServo2();
            }

#if DEBUG>2
            Serial.println(F("startDrawing command - noEraser executing"));
#endif
            // Pen lift
            moveServo2(SERVO2_LIFT);

            // Jason :: TODO: Trying to get rid of the dot!
            // moveServo1(SERVO1_NOERASER);
            moveServo1(SERVO1_ERASER);

            servo_counter++;
            if (servo_counter > 100) {
							Serial.println(F("done waiting for servos"));
              digitalWrite(4, LOW); // Enable motors...
              // Default move speed
              max_speed_x = MAX_SPEED_X;
              max_speed_y = MAX_SPEED_Y;
              erase_mode = 0;
              commands_index++;
              show_command = true;
              timeout_counter = 0;
              servo_counter = 0;
            }
          }
          else if (code1 == 4002) { // END DRAWING
            Serial.print(F(" !STOP DRAW; erase_mode: " ));
            Serial.print(erase_mode);
            Serial.print(F(", time: "));
            Serial.println(millis() - draw_init_time);
            // Pen lift
            if (!servo1_ready) {
              enableServo1();
              //Serial.println("EnableS1");
            }
            if (!servo2_ready) {
              enableServo2();
              //Serial.println("EnableS2");
            }
            moveServo1(SERVO1_ERASER);
            moveServo2(SERVO2_PAINT);
            digitalWrite(4, HIGH); // Disable motors...
            dir_x = 0;
            dir_y = 0;
            erase_mode = 0;
            draw_task = false;
            commands_index = 0;
            servo_counter = 0;
            delay(300);    // Nothing to do ??
            poll_again = true;
            if (code2 == 4010) {  // Special code? => timeout_recovery on next block
              timeout_recover = true;
              Serial.print(F("->Timeout recover mode!"));
            }
            else
              timeout_recover = false;
            //stopServo();
            disableServo1();
            disableServo2();
          }
          else if (code1 == 4003) { // Pen lift command
            if (!servo1_ready) {
              enableServo1();
            }
            if (!servo2_ready) {
              enableServo2();
            }
#if DEBUG>2
            Serial.println(F("penLift command - noEraser executing"));
#endif
            moveServo2(SERVO2_LIFT);
            moveServo1(SERVO1_NOERASER);
            servo_counter++;
            if (servo_counter > 90) {
							Serial.println(F("done waiting for servos"));
              erase_mode = 0;
              commands_index++;
              show_command = true;
              max_speed_x = MAX_SPEED_X;
              max_speed_y = MAX_SPEED_Y;
              Serial.println(F("  Pen lift, no eraser"));
              timeout_counter = 0;
              servo_counter = 0;
              disableServo2();
            }
          }
          // Pen down command
          else if (code1 == 4004) {
            if (!servo1_ready) {
              enableServo1();
            }
            if (!servo2_ready) {
              enableServo2();
            }
 
#if DEBUG>2
            Serial.println(F("penDown command - no eraser executing"));
#endif
            moveServo1(SERVO1_NOERASER);
            moveServo2(SERVO2_PAINT);
            servo_counter++;
            //Serial.println(servo_pos);
            if (servo_counter > 180) {
							Serial.println(F("done waiting for servos"));
              servo_pos2 = SERVO2_PAINT;
              erase_mode = 0;
              commands_index++;
              show_command = true;
              max_speed_x = SPEED_PAINT_X;
              max_speed_y = SPEED_PAINT_Y;
              Serial.println(F(" SP"));
              timeout_counter = 0;
              servo_counter = 0;
              disableServo2();
            }
          }
          // Eraser command
          else if (code1 == 4005) {
            if (!servo1_ready) {
              enableServo1();
            }
            if (!servo2_ready) {
              enableServo2();
            }
            // Make position correction for eraser
            setPosition_mm10(last_move_x + ERASER_OFFSET_X * 10, last_move_y + ERASER_OFFSET_Y * 10);
#if DEBUG>2
            Serial.println(F("eraser command - eraser executing"));
#endif
            moveServo1(SERVO1_ERASER);
            moveServo2(SERVO2_PAINT);
            servo_counter++;
            if (servo_counter > 350) {
							Serial.println(F("done waiting for servos"));
              servo_pos1 = SERVO1_ERASER;
              erase_mode = 1;

              commands_index++;
              show_command = true;
              max_speed_x = SPEED_ERASER_X;
              max_speed_y = SPEED_ERASER_Y;
              Serial.println(F(" SE"));
              timeout_counter = 0;
              servo_counter = 0;
              disableServo1();
              disableServo2();
            }
          }
          // Eraser down but no pause
          else if (code1 == 4007) {
            Serial.println(F("  Eraser down but no pause"));
            if (!servo1_ready) {
              enableServo1();
            }
            if (!servo2_ready) {
              enableServo2();
            }
            moveServo1(SERVO1_ERASER);
            moveServo2(SERVO2_PAINT);
            commands_index++;
            show_command = true;
            max_speed_x = SPEED_ERASER_X;
            max_speed_y = SPEED_ERASER_Y;
            timeout_counter = 0;
            servo_counter = 0;
          }
          // Wait command
          else if (code1 == 4006) {
            disableServo1();
            disableServo2();
            delay_counter++;
            if (code2 > 30) // maximun 30 seconds of wait
              code2 = 30;
            if (delay_counter > ((long)code2 * 1000)) { // Wait for code2 seconds
              Serial.println(F(" WM"));
              commands_index++;
              show_command = true;
              delay_counter = 0;
              timeout_counter = 0;
            }
          }
          else {
            if (servo1_ready)
              disableServo1();
            if (servo2_ready)
              disableServo2();
            timeout_counter = 0;
            // Send coordinates to robot in mm/10 units
            if (erase_mode == 1) { // In erase mode, we make the correction of the position of the eraser
              setPosition_mm10(code1 + ERASER_OFFSET_X * 10, code2 + ERASER_OFFSET_Y * 10);
              Serial.print("E");
            }
            else {
              if ((code1 < 10) && (code2 < 10)) { // Home position?
                setPosition_mm10(code1, code2);
                home_position = true;
              }
              else {
                setPosition_mm10(code1 + PAINT_OFFSET_X * 10, code2 + PAINT_OFFSET_Y * 10);
                home_position = false;
              }
            }
            last_move_x = code1;
            last_move_y = code2;
#if DEBUG>0
            Serial.print( F("target position; x: "));
            Serial.print(target_position_x);
            Serial.print(", y:");
            Serial.print(target_position_y);
            Serial.println();
#endif
            commands_index++;
            show_command = true;
          }

        }
        else {
          // End of commands...
          Serial.print(F(" !FINISH! time:"));
          Serial.println(millis() - draw_init_time);
          commands_index = 0;
          draw_task = false;
          disableServo1();
          disableServo2();
          servo_counter = 0;
          dir_x = 0;
          dir_y = 0;
        }
      }

#if DEBUG==3
      if ((loop_counter % 50) == 0) {
        Serial.print( F("Ongoing move; targetX: "));
        Serial.print( target_position_x );
        Serial.print( F(", position_x: "));
        Serial.print( position_x );
        Serial.print( F(", targetY: "));
        Serial.print( target_position_y );
        Serial.print( F(", position_y: "));
        Serial.println( position_y );
      }
#endif
    }  // draw task
    else {
      // Polling server, task for me?
      loop_counter = 0;
      poll_again = false;
      if (!home_position) {
        if (wait_counter == 0)
          wait_counter = millis();
        if ((millis() - wait_counter) > 8000) {
          // Force Go to home command
          Serial.println("->Force Home!");
          draw_task = true;
          new_packet = true;
          digitalWrite(4, LOW); // Enable motors...
          show_command = true;
          timeout_counter = 0;
          // ($code1>>4),(($code1<<4)&0xF0)|(($code2>>8)&0x0F),($code2&0xFF)
          // 4009,4000
          buffer[0] = (4009 >> 4);
          buffer[1] = ((4009 << 4) & 0xF0) | ((4000 >> 8) & 0x0F);
          buffer[2] = (4000 & 0xFF);
          // 4001,4001
          buffer[3] = (4001 >> 4);
          buffer[4] = ((4001 << 4) & 0xF0) | ((4001 >> 8) & 0x0F);
          buffer[5] = (4001 & 0xFF);
          // 4003,0000
          buffer[6] = (4003 >> 4);
          buffer[7] = ((4003 << 4) & 0xF0) | ((0 >> 8) & 0x0F);
          buffer[8] = 0;
          // 1,1
          buffer[9]  = 0;
          buffer[10] = ((1 << 4) & 0xF0) | 0;
          buffer[11] = 1;
          // 4002,4002
          buffer[12] = (4002 >> 4);
          buffer[13] = ((4002 << 4) & 0xF0) | ((4010 >> 8) & 0x0F);  // Special END 4002 4010 => timeout recover
          buffer[14] = (4010 & 0xFF);
          commands_lines = 5;
          draw_init_time = millis();
          return; // End
        }
      } // if(!home_position)
      delay(20);
      Serial.println();
      Serial.println(F("POLL server..."));
      ESPflush();
      if (block_number == -1) {
        // Ready for new blocks...
        strcpy(get_string, SERVER_URL);
        strcat(get_string, "?ID_IWBB=");
        strcat(get_string, MAC);
        strcat(get_string, "&STATUS=READY");
        response = ESPsendHTTP(get_string);
      } else {
        // ACK last block and ready for new one...
        strcpy(get_string, SERVER_URL);
        strcat(get_string, "?ID_IWBB=");
        strcat(get_string, MAC);
        strcat(get_string, "&STATUS=ACK&NUM=");
        char num[6];
        sprintf(num, "%d", block_number);
        strcat(get_string, num);
        response = ESPsendHTTP(get_string);
      }
      Serial.print(F("Made request to server; response: "));
      Serial.println(response);
      if (response) {
        message_readed = 0;
        message_status = 0;
        message_timer_init = millis();
        while (message_readed == 0)
          ESPwaitforMessage(30);
        if (message_readed == 2) {
          Serial.println(F("!ERROR: M Timeout"));
          Network_errors++;
          // if we have three or more consecutive Network errors we reset wifi connection
          if (Network_errors >= 3) {
            Serial.print(F("Too much network errors: Reseting..."));
            Network_errors = 0;
            digitalWrite(13, LOW);
            // Reset module
            Serial1.println();
            ESPflush();
            Serial1.println(F("AT+RST"));
            ESPwaitFor("ready", 10);
            if (WifiConnect()) {
              digitalWrite(13, HIGH);
            }
            else {
              Serial.print(F("Error trying to reconnect!"));
              digitalWrite(13, LOW);
            }
          }
        }
        else if (message_size < 6) {
          Network_errors = 0;
          Serial.print(F("Data size:"));
          Serial.println(message_size);
          if (message_size > 0) {
            Serial.print(F("Message:"));
            Serial.print((char)buffer[0]);
            Serial.println((char)buffer[1]);
          }
          block_number = -1;
          // Error message?
          if (buffer[0] == 'E') {
            Serial.println("Error Message!");
            Serial.println("Wait for next request...");
            delay(10000);
            // Something more here??
          }
          delay(100);
        }
        else {
          Network_errors = 0;
          Serial.print(F("main - got message; size: "));
          Serial.print(message_size);
          commands_lines = message_size / 3;
          Serial.print(F(", commands: "));
          Serial.println(commands_lines);
          commands_index = 0;
          if (message_size == MAX_PACKET_SIZE) {
            Serial.println(F("main - more blocks expected;"));
          }
          draw_task = true;
          new_packet = true;
          digitalWrite(4, LOW); // Enable motors...
          show_command = true;
          timeout_counter = 0;
          draw_init_time = millis();
        }
      } // if (response)
    } // draw task
  } // 1Khz loop
}
