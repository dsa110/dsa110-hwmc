print("Starting DSA-110 antenna control script")
local ver = 3.004
print(string.format("Ver. %.3f", ver))

-- NOTE: Treat as binary in Git since newline must use Windows convention
-- Modbus registers used:
--
-- 02009: bit to turn drive on for north motion.
-- 02010: bit to turn drive on for south motion.
-- 00026: AIN13, encoder voltage reading.
-- 07000: Averaged AIN13 reading.
-- 46180: command from control system.
-- 46181: current state machine state.
-- 46182: debug register.
-- 46000: version number.
-- 46002: new position to acquire, deg.
-- 46004: current position, deg.
-- 46006: error, deg.
-- 46008: averaged normalised raw inclinometer reading, V.

-- Immediately make sure digital outputs are in a safe state
MB.W(2601, 0, 30)        -- Set EIO digital to outputs as required.
MB.W(2501, 0, 24)        -- Set drive and noise diode initial states (off).

-- Create required local variables.

local timeStep = 25       -- Time step of the loop, ms.
local maxPause = 50       -- Time steps to pause before retrying.
local pauseCount = 0      -- Counter for pause
local goal = 0            -- Goal elevation angle, deg.
local actual = 0          -- Encoder reading, deg.
local err = 0             -- Position error
local nAvg = 90           -- Number of encoder readings to average
local nSamp = 200         -- Number of supply voltages samples to average
local rate = 1570.0       -- Elevation rate, ms per degree.
local farTol = 0.8        -- Allowable error for initial stop, deg.
local nearTol = 0.05      -- Allowable error in final position, deg.
local tol = farTol        -- Tolerance value in effect, deg.
local minTimeout = 30000  -- Minimum time before declaring timeout.
local timeout = 0         -- Time left to timeout, based on rate, error (ms)
local fwLimN = 135        -- Firmware limit, north, deg
local fwLimS = 3.0        -- Firmware limit, south, deg

-- Variables associated with state machine.
local states = {['halt'] = 0, ['seek'] = 1, ['acquired'] = 2,
                ['timeout'] = 3, ['fwLimN'] = 4, ['fwLimS'] = 5}
local state = states.halt
local cmd = 0
local dir = 'h'

-- Read inclinometer calibration values from flash
MB.W(61810, 1, 0)
local vScale = MB.R(61812, 3)
MB.W(61810, 1, 4)
local vOff = MB.R(61812, 3)
MB.W(61810, 1, 8)
local aOff = MB.R(61812, 3)
MB.W(61810, 1, 12)
local collim = MB.R(61812, 3)
local angOff = aOff + collim

-- Check for 'bad' (initialized) values

if (math.abs(vScale - 2.0) > 0.25) or (math.abs(vOff - 2.5) > 0.25) then
    vScale = 2.0
    vOff = 2.5
    angOff = 0.0
end

-- Write to registers so they can be read by control system
MB.W(46010, 3, vScale)
MB.W(46012, 3, vOff)
MB.W(46014, 3, angOff)
MB.W(46016, 3, aOff)
MB.W(46018, 3, collim)

-- Create local names for functions.
local checkInterval = LJ.CheckInterval
local mbRead = MB.R
local mbWrite = MB.W
local abs = math.abs
local acos = math.acos
local deg = math.deg

-- Create new local functions.
local function halt()
  mbWrite(2009, 0, 0)
  mbWrite(2010, 0, 0)
  return 'h'
end

local function north()
  mbWrite(2010, 0, 0)
  mbWrite(2009, 0, 1)
  return 'n'
end

local function south()
  mbWrite(2009, 0, 0)
  mbWrite(2010, 0, 1)
  return 's'
end

-- Function for conversion of Level Developments SAS-90-R inclinometer.
-- Set up to average multiple readings.
local samples = {}  -- Storage for supply samples to average (1 per second)
local cur = 1       -- Initialize current sample pointer
for i = 1, nSamp, 1
do
  samples[i] = mbRead(24, 3)  -- Fill with current value so not averaging 0's
end

local gain = 1/vScale
local function encoderRead()
    local cosval = 0
    samples[cur] = mbRead(24, 3)
    cur = cur + 1
    if cur > nSamp then
        cur = 1
    end
    local vs = 0
    for i = 1, nSamp, 1
    do
        vs = vs + samples[i]
    end
    local corr = 5.0 * nSamp / vs
    local rdg = corr * mbRead(7026, 3)
    mbWrite(46008, 3, rdg)
    cosval = (rdg - vOff) * gain
    if cosval > 1 then
        cosval = 1
    end
    if cosval < -1 then
        cosval = -1
    end
    local angle = deg(acos(cosval)) - angOff
    return angle
end

mbWrite(46000, 3, ver)      -- Write code version number into register.

mbWrite(2601, 0, 30)        -- Set EIO digital to outputs as required.
mbWrite(2501, 0, 24)        -- Set drive and noise diode initial states (off).
mbWrite(46180, 0, 0)        -- Make sure no command is active.
mbWrite(9026, 1, 3)         -- Set AIN13 to min, max, average.
mbWrite(9326, 1, nAvg)      -- Set AIN13 number of samples.
mbWrite(10226, 3, 6000)     -- Set AIN13 scan rate.

dir = halt()                -- Motor off.

LJ.IntervalConfig(0, timeStep)  -- Set loop interval.
local dt = 0.000025
local t = 0
local drive = 0

while true do
  if checkInterval(0) then
      -- Interval completed.
      -- Check for new command.
      cmd = mbRead(46180, 0)
      mbWrite(46180, 0, 0)
      goal = mbRead(46002, 3)
      actual = encoderRead()
      err = goal - actual
      mbWrite(46004, 3, actual)
      mbWrite(46006, 3, err)

      -- If new command, execute it.
      if cmd == 1 then
          --> Halt motor.
          state = states.halt
          dir = halt()

      elseif cmd == 2 then
          --> Move to goal.
          state = states.seek
          t = 0
          dt = 0.001 * timeStep
          tol = farTol
          timeout = 1.05 * abs(err) * rate + minTimeout
          pauseCount = maxPause
          if err > 0 then
            dir = north()
          else
            dir = south()
          end
      end

    cmd = 0
    
    -- Motion state machine. 
    mbWrite(46181, 0, state)       -- Record current state in user MB register.
    if state > 0 then
      drive = mbRead(2014) + 2 * mbRead(2015)
    end

    if state == states.halt then
      dir = halt()
      
    elseif state == states.seek then
      if dir == 'n' then
        if actual >= fwLimN then
          state = states.fwLimN
          dir = halt()
        elseif err < tol then
          dir = halt()
          tol = nearTol
          pauseCount = maxPause
        end

      elseif dir == 's' then
        if actual <= fwLimS then
          state = states.fwLimS
          dir = halt()
        elseif err > -tol then
          dir = halt()
          tol = nearTol
          pauseCount = maxPause
        end

      elseif pauseCount == 0 then
        if abs(err) < tol then
          dir = halt()
          state = states.acquired
        else
          if err > 0 then
            dir = north()
          else
            dir = south()
          end
        end
      end

      pauseCount = pauseCount - 1

      timeout = timeout - timeStep
      if timeout <= 0 then
        dir = halt()
        state = states.timeout
      end
    
    elseif state == states.acquired then
      dir = halt()
  
    elseif state == states.timeout then
      dir = halt()
    end
    collectgarbage("collect")
  end
end
