# standalone_app.py
# -*- coding: utf-8 -*-
#
# (독립모드 엔트리)
# 중요!! 파이썬 환경 > Conda > myenv37 선택해서 실행해야함
# (myenv37) D:\Work_Jain\Python\KLF10_Modbus>python standalone_app.py
#   장치번호:1, function code:0x04 Read Input Registers
#   주소(Hex): 0001, 길이: 6, Write 데이터: 그대로
#   >> Real-time velocity 읽히면 정상    
#
from __future__ import annotations

from gui_app import ModbusToolApp

if __name__ == "__main__":
    app = ModbusToolApp()
    app.mainloop()

#
# end of file
#