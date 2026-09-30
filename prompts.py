'''
============================== ============================== ==============================
[요구사항]

Modbus binary 로 통신하는 프로그램을 만들어 주세요.
통신 하드웨어는 RSa485 USB 동글 입니다.
소프트웨어는 다른 함수로부터 호출되는 서브모드와 단독으로 실행하는 독립모드의, 2가지 모드가 있는 구조 입니다.
GUI, Serial Port 통신, Modbus 프로토콜 구현, Modbus CRC 계산, 서브모드, 독립모드 를 각각 별도의 파일로 구현해주세요.

1. 서브모드에서는 다음의 함수들을 구현해주세요. 
   1-1. Get_Active_SerialPort 함수는 현재 유효한 Serial Port 리스트를 반환합니디.
   1-2. Set_SerialPort 함수는 baud rate, Parity, Stop Bit, 모두 3개의 파라미터를 받아서 별도의 변수에 저장합니다.
      1-2-1. baud rate 는 int 형으로 받고 4800, 9600, 38400, 115200 등 popular 한 통신 baud rate 중 하나만 받도록 구현해주세요.
      1-2-2. Parity 는 "N", "E", "O" 중 하나의 문자로 받고 "N"은 None, "E"는 Even, "O"는 Odd 를 의미하도록 구현해주세요.
      1-2-3. Stop Bit 는 1, 2 중 하나의 int 형으로 받고 1은 1 Stop Bit, 2는 2 Stop Bit 를 의미하도록 구현해주세요.
   1-3. Open_SerialPort 함수는 Serial Port 번호를 파라미터로 받아서 저장합니다.
      1-3-1. 이미 열린 Serial Port 가 없으면 저장된 Serial Port 번호의 Port를 열고 
      1-3-2. 저장된 baud rate, Parity, Stop Bit를 사용해서 port를 설정합니다.
      1-3-3. 성공이나 실패를 bool로 회신합니다.
   1-4. Serial Port 열기가 성공하면 별도의 수신 쓰레드와 1KB 크기의 Circular 수신 버퍼를 만들고 수신이 있는지 검사해서 수신된 데이터를 버퍼에 저장합니다.
      1-4-1. Get_Modbus_Reveive_Data 함수로 수신한 data와 byte 수를 반환합니다. 수신한 데이터는 Modbus binary 프로토콜 형식입니다. 
      1-4-2. Send_Modbus_Transmit_Data 함수로 송신할 data와 byte 수를 받아서 Modbus binary 프로토콜로 변환한 다음 Serial Port로 송신합니다.
   1-5. Close_SerialPort 함수는 Port를 닫고 수신 쓰레드를 종료하고 Circular 수신 버퍼를 free합니다.

2. 독립모드에서는 포트 설정 창과 장치 통신 창이 있습니다. GUI와 서브모드에서 구현한 함수들을 사용해서 다음의 기능들을 구현해주세요.
   2-1. 포트 설정 창에는  Serial Port 메뉴, Baudrate 메뉴, 포트 열기 버튼, 포트 닫기 버튼,  통신 상태 창이 있습니다.
      2-1-1.  Serial Port 메뉴는 Get_Active_SerialPort 함수로 얻은 포트 번호 중 하나를 선택하는 기능을 구현해주세요.
      2-1-2.  Baudrate 메뉴는 4800, 9600, 38400, 115200 등 popular 한 통신 baud rate 중 하나를 선택하는 기능을 구현해주세요.
      2-1-3.  포트 열기 버튼은 위에서 설정한 parameter 로 Set_SerialPort 함수와 Open_SerialPort 함수를 호출해주세요.
      2-1-4.  포트 닫기 버튼은 Close_SerialPort 함수를 호출해주세요.
      2-1-5.  통신 상태 창에는 현재 Serial Port가 열려있는지 닫혀있는지를 표시해주세요.
   2-2. 장치 통신 창에는  장치 번호 메뉴, function code 메뉴, 주소 설정 메뉴, 길이 설정 메뉴,  통신 상태 메뉴,  데이터 표시 창 이있습니다.
      2-2-1.  장치 번호 메뉴는 1부터 16까지 숫자 중 하나를 선택해서 Device_ID 변수에 저장하는 기능을 구현하고
      2-2-2.  function code 메뉴는 "1.Coil Status", "2.Input Status", "3.Holding Reg", "4.Input Reg." 중 하나를 선택해서 Function_Code 변수에 저장하는 기능을 구현하고
      2-2-3.  주소 설정 메뉴는 사용자의 임의의 16진수 숫자를 입력 받아서 Address 변수에 저장하는 기능을 구현하고
      2-2-4.  길이 설정 메뉴는 사용자의 임의의 16진수 숫자를 입력 받아서 Length 변수에 저장하는 기능을 구현하고
      2-2-5.  통신 상태 창에는 송신창과 수신창을 만들고 
         2-2-5-1. 송신창에는 마지막으로 송신한 데이터 열을 16진수로 표시하고 
         2-2-5-2. 수신창에는 마지막으로 수신한 데이터 열을 16진수로 표시하고 마지막 송신에 대한 응답이 없으면 "--"로 표시해주세요.
      2-2-6.  데이터 표시 창에는 수신한 데이터 중에서 내용"만 address:data" 형식으로 표시합니다.

[응답]

   동작 요약(요구사항 매핑)
   ✅ 서브모드

   Get_Active_SerialPort() : 활성 포트 리스트 반환

   Set_SerialPort(baud, parity, stopbit) : 검증 후 저장(baud는 popular만 허용, parity N/E/O, stop 1/2)

   Open_SerialPort(port) : 저장된 설정으로 포트 오픈 + RX Thread + 1KB CircularBuffer 생성

   Get_Modbus_Reveive_Data() : 버퍼에서 수신 데이터 및 바이트 수 반환(consume)

   Send_Modbus_Transmit_Data(data, n) : CRC 붙여 RTU 프레임 생성 후 송신

   Close_SerialPort() : 포트 닫고 쓰레드 종료 + 버퍼 free

   ✅ 독립모드 GUI

   포트 설정 탭:

   Serial Port 메뉴: Get_Active_SerialPort() 결과 중 선택

   Baudrate 메뉴: popular baud 중 선택

   포트 열기: Set_SerialPort() + Open_SerialPort()

   포트 닫기: Close_SerialPort()

   통신 상태: 열림/닫힘 표시

   장치 통신 탭:

   장치 번호(1~16), function code(1~4), 주소/길이(HEX)

   송신/수신 마지막 프레임 HEX 표시(응답 없으면 RX는 --)

   데이터 표시: 응답 내용을 address:data 형식으로만 출력


============================== ============================== ==============================
[요구사항]

변경할 부분이 있습니다.
   2-2. 장치 통신 창에는 장치 번호 메뉴, function code 메뉴, 주소 설정 메뉴, 길이 설정 메뉴, Write 데이터 설정 메뉴, 통신 상태 메뉴, 데이터 표시 창 이있습니다.
      2-2-1.  장치 번호 메뉴는 1부터 16까지 숫자 중 하나를 선택해서 Device_ID 변수에 저장하는 기능을 구현하고
      2-2-2.  function code 메뉴는 "1.Coil Status", "2.Input Status", "3.Holding Reg", "4.Input Reg." 중 하나를 선택해서 Function_Code 변수에 저장하는 기능을 구현하고
      2-2-3.  주소 설정 메뉴는 사용자의 임의의 16진수 숫자를 입력 받아서 Address 변수에 저장하는 기능을 구현하고
      2-2-4.  길이 설정 메뉴는 사용자의 임의의 10진수 숫자를 입력 받아서 Length 변수에 저장하는 기능을 구현하고
      2-2-5.  Write 데이터 설정 메뉴는 사용자의 임의의 16진수 숫자를 최대 4개 입력 받아서 Payload[] 변수에 저장하는 기능을 구현하고
      2-2-6.  "요청 전송" 버튼이 눌리면 Send_Modbus_Transmit_Data(Length, Paylod) 를 호출해 주세요
      2-2-7.  통신 상태 창에는 송신창과 수신창을 만들고 
         2-2-7-1. 송신창에는 마지막으로 송신한 데이터 열을 16진수로 표시하고 
         2-2-7-2. 수신창에는 마지막으로 수신한 데이터 열을 16진수로 표시하고 마지막 송신에 대한 응답이 없으면 "--"로 표시해주세요.
      2-2-6.  데이터 표시 창에는 수신한 데이터 중에서 내용"만 address:data" 형식으로 표시합니다.

[응답]
OK
============================== ============================== ==============================
[문제점] 모드버스 CRC 오류

[요구사항]
Modbus CRC 계산이 틀립니다. 
{0x01, 0x04, 0x01, 0x02, 0x00, 0x02, 0xD1, 0xF7} 에서 앞 6 바이트 CRC 계산하면 마지막 2 바이트가 나와야 합니다. 
{0x01, 0x04, 0x04, 0x81, 0xB3, 0x41, 0xCF, 0x52, 0x5B} 에서는 앞 7 바이트 CRC 계산하면 마지막 2 바이트가 나와야 합니다. 
코드 수정하고 검증해주세요.

[응답]
OK

============================== ============================== ==============================
[문제점] 데이터의 내용 지정

[요구사항]
변경할 부분이 있습니다.
   2-2. 장치 통신 창에는 장치 번호 메뉴, function code 메뉴, 주소 설정 메뉴, 길이 설정 메뉴, Write 데이터 설정 메뉴, 통신 상태 메뉴, 데이터 표시 창, 항목 표시 창이 있습니다.
      2-2-1.  장치 번호 메뉴는 1부터 16까지 숫자 중 하나를 선택해서 Device_ID 변수에 저장하는 기능을 구현해주세요.
      2-2-2.  function code 메뉴는 "1.Coil Status", "2.Input Status", "3.Holding Reg", "4.Input Reg." 중 하나를 선택해서 Function_Code 변수에 저장하는 기능을 구현해주세요.
      2-2-3.  주소 설정 메뉴는 사용자의 임의의 16진수 숫자를 입력 받아서 Address 변수에 저장하는 기능을 구현해주세요.
      2-2-4.  길이 설정 메뉴는 사용자의 임의의 10진수 숫자를 입력 받아서 Length 변수에 저장하는 기능을 구현해주세요.
      2-2-5.  Write 데이터 설정 메뉴는 사용자의 임의의 16진수 숫자를 2개 입력 받아서 Payload[] 변수에 저장합니다.
         2-2-5-1. 16 bit 정수 변수 request_length에 Payload[] 2 byte를 big-endian 으로 변경해서 저장해주세요. 
      2-2-6.  "요청 전송" 버튼이 눌리면 Send_Modbus_Transmit_Data(Length, Paylod) 를 호출해 주세요.
      2-2-7.  통신 상태 창에는 송신창과 수신창을 만들고 
         2-2-7-1. 송신창에는 마지막으로 송신한 데이터 열을 16진수로 표시하고 
         2-2-7-2. 수신창에는 마지막으로 수신한 데이터 열을 16진수로 표시하고 마지막 송신에 대한 응답이 없으면 "--"로 표시해주세요.
      2-2-8.  데이터 표시 창에는 수신한 데이터 중에서 내용"만 address:data" 형식으로 표시합니다.data는 16bit 의 16진수로 표시해주세요.
      2-2-9.  항목 표시 창에는 "title:value" 형식으로 표시합니다.
         2-2-9-1. "title" 은 address 에 해당하는 문자열 입니다.
         2-2-9-2. 다음 공통 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  공통 Address to Title mapping:
                  0x0001 "Real-time velocity"
                  0x0003 "Average velocity"
                  0x0102 "Instantaneous flow rate"
                  0x0105 "Cumulative flow"
                  0x010B "Empty height"
                  0x010D "Water level"
                  0x2251 "Water level sensor range"
                  0x2253 "Low level adjustment"
                  0x2255 "High level adjustment"
                  0x2257 "Blind zone"
                  0x2259 "Distance offset"
                  
         2-2-9-3. 0x220F Address의 title은 "Channel flowcalculationmodel" 입니다. 
                  이 값은 2byte만 사용해서 16bit 정수로 변환해서 0, 1, 2, 3, 4, 5 중 하나가 됩니다.
                  숫자별 title mapping:
                     0: "Rectangular"
                     1: "Trapezoidal"
                     2: "Rectangular–Trapezoidal"
                     3: "DoubleTrapezoidal"
                     4: "U-shaped"
                     5: "Irregula"
                        
         2-2-9-4. "Channel flowcalculationmodel" 이 [0: "Rectangular"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Rectangular-channel width"
                  0x2205 "Rectangular-channel height"
                  0x2203 "Rectangular-distance from flow meter to channel wall"
                  
         2-2-9-5. "Channel flowcalculationmodel" 이 [1: "Trapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Trapezoidal channel top width"
                  0x2203 "Trapezoidal channel bottom width"
                  0x2205 "Trapezoidal channel height"
                  0x2207 "Trapezoidal-distance from flowmeter to channel wall"

         2-2-9-6. "Channel flowcalculationmodel" 이 [2: "Rectangular–Trapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Rectangular-trapezoidal channel top width"
                  0x2203 "Rectangular-trapezoidal channel bottom width"
                  0x2205 "Rectangular-trapezoidal channel upper height"
                  0x2207 "Rectangular-trapezoidal channel lower height"
                  0x2209 "Rectangular-trapezoidal-distance from flowmeter to channel wall"

         2-2-9-7. "Channel flowcalculationmodel" 이 [3: "DoubleTrapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Double trapezoidal channel top width"
                  0x2203 "Double trapezoidal channel middle width"
                  0x2205 "Double trapezoidal channel bottom width"
                  0x2207 "Double trapezoidal channel upper height"
                  0x2209 "Double trapezoidal channel lower height"
                  0x220B "Double trapezoidal-distance from flowmeter to channel wall"

         2-2-9-8. "Channel flowcalculationmodel" 이 [4: "U-shaped"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "U-shaped channel width"
                  0x2203 "U-shaped channel height"
                  0x2201 "Distance from flow meter to irregular channel wall"

         2-2-9-9. "Channel flowcalculationmodel" 이 [5: "Irregula"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2203 "Irregular channel width"
                  0x2271 "Irregular-bottom elevation"

[응답]
OK

============================== ============================== ==============================
[문제점] 데이터의 내용 지정

[요구사항]
변경할 부분이 있습니다.
      2-2-2.  function code 메뉴는 다음 8개 중 하나를 선택해서 Function_Code 변수에 저장하는 기능을 구현해주세요.
         2-2-2-1. function code는 "0x01:Read Coil Status", "0x02:Read Input Status", "0x03:Read Holding Reg", "0x04:Read Input Reg.", 
                  "0x06:Write Integer", "0x10:Write Floating Point", "0x41:Clear the Cumulative".

[응답]
OK

============================== ============================== ==============================
[문제점] Write 기능 추가 -- not yet implemented

[요구사항]
변경할 부분이 있습니다.
   2-2. 장치 통신 창에는 장치 번호 메뉴, function code 메뉴, 주소 설정 메뉴, 길이 설정 메뉴, Write 데이터 설정 메뉴, 통신 상태 메뉴, 데이터 표시 창, 항목 표시 창이 있습니다.
      2-2-1.  장치 번호 메뉴는 1부터 16까지 숫자 중 하나를 선택해서 Device_ID 변수에 저장하는 기능을 구현해주세요.
      2-2-2.  function code 메뉴는 다음 8개 중 하나를 선택해서 Function_Code 변수에 저장하는 기능을 구현해주세요.
         2-2-2-1. function code는 "0x01:Read Coil Status", "0x02:Read Input Status", "0x03:Read Holding Reg", "0x04:Read Input Reg.", 
                  "0x06:Write Integer", "0x10:Write Floating Point", "0x41:Clear the Cumulative".
      2-2-3.  주소 설정 메뉴는 사용자의 임의의 16진수 숫자를 입력 받아서 Address 변수에 저장하는 기능을 구현해주세요.
      2-2-4.  길이 설정 메뉴는 사용자의 임의의 10진수 숫자를 입력 받아서 Length 변수에 저장하는 기능을 구현해주세요.
      2-2-5.  Write 데이터 설정 메뉴는 사용자의 임의의 16진수 숫자를 2개 입력 받아서 Payload[] 변수에 저장합니다.
         2-2-5-1. 16 bit 정수 변수 request_length에 Payload[] 2 byte를 big-endian 으로 변경해서 저장해주세요. 
      2-2-6.  "요청 전송" 버튼이 눌리면 Send_Modbus_Transmit_Data(Length, Paylod) 를 호출해 주세요.
      2-2-7.  통신 상태 창에는 송신창과 수신창을 만들고 
         2-2-7-1. 송신창에는 마지막으로 송신한 데이터 열을 16진수로 표시하고 
         2-2-7-2. 수신창에는 마지막으로 수신한 데이터 열을 16진수로 표시하고 마지막 송신에 대한 응답이 없으면 "--"로 표시해주세요.
      2-2-8.  데이터 표시 창에는 수신한 데이터 중에서 내용"만 address:data" 형식으로 표시합니다.data는 16bit 의 16진수로 표시해주세요.
      2-2-9.  항목 표시 창에는 "title:value" 형식으로 표시합니다.
         2-2-9-1. "title" 은 address 에 해당하는 문자열 입니다.
         2-2-9-2. 다음 공통 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  공통 Address to Title mapping:
                  0x0001 "Real-time velocity"
                  0x0003 "Average velocity"
                  0x0102 "Instantaneous flow rate"
                  0x0105 "Cumulative flow"
                  0x010B "Empty height"
                  0x010D "Water level"
                  0x2251 "Water level sensor range"
                  0x2253 "Low level adjustment"
                  0x2255 "High level adjustment"
                  0x2257 "Blind zone"
                  0x2259 "Distance offset"
                  
         2-2-9-3. 0x220F Address의 title은 "Channel flowcalculationmodel" 입니다. 
                  이 값은 2byte만 사용해서 16bit 정수로 변환해서 0, 1, 2, 3, 4, 5 중 하나가 됩니다.
                  숫자별 title mapping:
                     0: "Rectangular"
                     1: "Trapezoidal"
                     2: "Rectangular–Trapezoidal"
                     3: "DoubleTrapezoidal"
                     4: "U-shaped"
                     5: "Irregula"
                        
         2-2-9-4. "Channel flowcalculationmodel" 이 [0: "Rectangular"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Rectangular-channel width"
                  0x2205 "Rectangular-channel height"
                  0x2203 "Rectangular-distance from flow meter to channel wall"
                  
         2-2-9-5. "Channel flowcalculationmodel" 이 [1: "Trapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Trapezoidal channel top width"
                  0x2203 "Trapezoidal channel bottom width"
                  0x2205 "Trapezoidal channel height"
                  0x2207 "Trapezoidal-distance from flowmeter to channel wall"

         2-2-9-6. "Channel flowcalculationmodel" 이 [2: "Rectangular–Trapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Rectangular-trapezoidal channel top width"
                  0x2203 "Rectangular-trapezoidal channel bottom width"
                  0x2205 "Rectangular-trapezoidal channel upper height"
                  0x2207 "Rectangular-trapezoidal channel lower height"
                  0x2209 "Rectangular-trapezoidal-distance from flowmeter to channel wall"

         2-2-9-7. "Channel flowcalculationmodel" 이 [3: "DoubleTrapezoidal"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "Double trapezoidal channel top width"
                  0x2203 "Double trapezoidal channel middle width"
                  0x2205 "Double trapezoidal channel bottom width"
                  0x2207 "Double trapezoidal channel upper height"
                  0x2209 "Double trapezoidal channel lower height"
                  0x220B "Double trapezoidal-distance from flowmeter to channel wall"

         2-2-9-8. "Channel flowcalculationmodel" 이 [4: "U-shaped"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2201 "U-shaped channel width"
                  0x2203 "U-shaped channel height"
                  0x2201 "Distance from flow meter to irregular channel wall"

         2-2-9-9. "Channel flowcalculationmodel" 이 [5: "Irregula"]인 경우 Address는 다음과 같이 mapping됩니다. 
                  각 Address 들의 "value"는 수신한 데이터 열 4byt를 32 bit float 로 변환한 값입니다. 변환 순서는 [2][3][0][1] 순서로 변환해주세요.
                  0x2203 "Irregular channel width"
                  0x2271 "Irregular-bottom elevation"

[응답]
not yet implemented



============================== ============================== ==============================
============================== ============================== ==============================
============================== ============================== ==============================
============================== ============================== ==============================
============================== ============================== ==============================

============================== END ==============================
'''