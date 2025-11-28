@echo off
TITLE Sysmon Hybrid AI - Control Panel
CLS

ECHO =========================================================
ECHO      SYSMON HYBRID CNN-TRANSFORMER CONTROL PANEL
ECHO =========================================================
ECHO.
ECHO  [1] Build Docker Image
ECHO  [2] Train Model (inside Docker)
ECHO  [3] Evaluate Model (inside Docker)
ECHO  [4] Collect Real Data (Host Windows)
ECHO  [5] Generate Synthetic Data (Host Windows)
ECHO  [6] Exit
ECHO.

SET /P M=Type 1, 2, 3, 4, 5, or 6 then press ENTER: 

IF %M%==1 GOTO BUILD
IF %M%==2 GOTO TRAIN
IF %M%==3 GOTO EVAL
IF %M%==4 GOTO COLLECT
IF %M%==5 GOTO GEN
IF %M%==6 GOTO EOF

:BUILD
ECHO Building Docker Image...
docker-compose build
PAUSE
GOTO EOF

:TRAIN
ECHO Starting Training...
docker-compose run --rm train
PAUSE
GOTO EOF

:EVAL
ECHO Starting Evaluation...
docker-compose run --rm evaluate
PAUSE
GOTO EOF

:COLLECT
ECHO Collecting Data (Requires Admin)...
python src/tt_collector.py
PAUSE
GOTO EOF

:GEN
ECHO Generating Logic Trap Data...
python src/logic_trap.py
python src/data.py
PAUSE
GOTO EOF

:EOF
EXIT