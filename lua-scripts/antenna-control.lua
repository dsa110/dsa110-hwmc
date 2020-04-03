print("Starting DSA-110 antenna control script")
local ver = 0.062
print(string.format("Ver. %.3f", ver))

-- Modbus registers used:
--
-- 2009:    bit to turn drive on for north motion
-- 2010:    bit to turn drive on for south motion
-- 26:      AIN13 (encoder voltage reading)
-- 46180:   command from control system
-- 46181:   current state machine state
-- 46182:   debug register
-- 46000:   version number
-- 46002:   new position to acquire (deg)
-- 46004:   current position (deg)
-- 46006:   error (deg)

-- Create required local variables.

local timeStep = 25   -- Time step of the loop in ms.
local maxPause = 50   -- Time steps to pause before retrying.
local pauseCount = 0  -- Counter for pause
local goal = 0        -- Goal elevation angle (deg).
local actual = 0      -- Encoder reading (deg).
local alt = 0
local err = 0         -- Position error
local nAvg1 = 1       -- Number of encoder readings to average
local nAvg2 = 14      -- Number of alt encoder readings to average
local eScale = 45.0   -- Encoder volts to deg scale factor.
local eOff = -22.5    -- Nominal encoder offset.
local eOffAdj = -1.08  -- Encoder zero correction.
local rate = 1570.0   -- Elevation rate (ms per degree).
local farTol = 0.8    -- Allowable error for initial stop (deg).
local nearTol = 0.05  -- Allowable error in final position (deg).
local tol = farTol    -- Tolerance value in effect (deg).
local minTimeout = 30000 -- Minimum time before declaring timeout.
local timeout = 0	  -- Time left to timeout, based on rate, error (ms)
local fwLimN = 135	  -- Firmware limit, north (deg)
local fwLimS = 3.0	  -- Firmware limit, south (deg)
local resIndex = 8
local settle = 0


-- Variables associated with state machine.

local states = {['halt'] = 0, ['seek'] = 1, ['acquired'] = 2,
                  ['timeout'] = 3, ['fwLimN'] = 4, ['fwLimS'] = 5}
local state = states.halt
local cmd = 0
local dir = 'h'

-- Create local functions.
local checkInterval = LJ.CheckInterval
local mbRead=MB.R
local mbWrite=MB.W
local abs = math.abs
local asin = math.asin
local deg = math.deg
local getTick = LJ.Tick
local lastTick
local nowTick
local format = string.format
-- local collectgarbage = LJ.collectgarbage

local function halt()
  mbWrite(2009, 0, 0)
  mbWrite(2010, 0, 0)
  return 'h'
end

local function north()
  mbWrite(2009, 0, 1)
  mbWrite(2010, 0, 0)
  return 'n'
end

local function south()
  mbWrite(2009, 0, 0)
  mbWrite(2010, 0, 1)
  return 's'
end

local function encoderRead()
  local rdg = 0.0
  for i = 1, nAvg1, 1
  do
    rdg = rdg + mbRead(26, 3)
  end
  return eScale * (rdg/nAvg1) + eOff + eOffAdj
end

local samples = {}
local cur = 1
local nSamp = 10
local sum = 0
samples = {}
for i = 1, nSamp, 1
do
  samples[i] = mbRead(24, 3)
end

mbWrite(41500, 0, resIndex)     -- Set resolution index (number of readings)
mbWrite(42000, 3, settle)       -- Set settling tim, us

local function altEncoderRead()
  local gain = 0.5200920306534157
  local offs = 2.4718043343090720
  local zero = 89.9649551257356400
  local sinval = 0

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
  corr = 5.0 * nSamp/vs
--[
  rdg = mbRead(7000, 3)
--  print(0.000025 * (getTick() - lastTick))
--[
  sinval = (rdg - offs)*gain
  if sinval > 1 then sinval = 1 end
  if sinval < -1 then sinval = -1 end
  local angle = deg(asin(sinval)) + zero
--]]

--print(format("%6d %6.4f", mbRead(41500, 0, mbRead(42000, 3))))
--]]
--[[
  rdg = mbRead(7002, 3)
  local angle = 68.7459329 * rdg - 74.7492862
--]]
  return angle
end

mbWrite(46000, 3, ver)          -- Write version number into register
mbWrite(2601, 0, 30)            -- Set EIO digital to outputs as required
mbWrite(2501, 0, 24)            -- Set drive and noise diode initial states
mbWrite(46180, 0, 0)            -- Make sure no command is active
-- mbWrite(41500, 0, resIndex)     -- Set resolution index (number of readings)
-- mbWrite(42000, 3, settle)       -- Set settling time before ADC read, us
mbWrite(41513, 0, resIndex)     -- Set resolution index (number of readings)
mbWrite(42013, 3, settle)       -- Set settling time before ADC read, us
mbWrite(41500, 0, 1)     -- Set resolution index (number of readings)
mbWrite(42000, 3, 0)       -- Set settling time before an ADC read, us
--[
mbWrite(9000, 1, 3)                -- Set AIN0 to min, max, average
mbWrite(9300, 1, 100)              -- Set AIN0 number of samples
mbWrite(10200, 3, 6000)            -- Set AIN0 scan rate
--]]
--[
mbWrite(9002, 1, 3)                -- Set AIN1 to min, max, average
mbWrite(9302, 1, 100)              -- Set AIN1 number of samples
mbWrite(10202, 3, 6000)            -- Set AIN1 scan rate
--]]
dir = halt()                    -- Motor off

LJ.IntervalConfig(0, timeStep)  -- Set loop interval
local dt = 0.000025
local t = 0
local drive = 0
lastTick = getTick()
local count = 40

while true do
  if checkInterval(0) then  -- Interval completed
    t = t + dt
    -- Check for new command
    cmd = mbRead(46180, 0)
    mbWrite(46180, 0, 0)
    goal = mbRead(46002, 3)
    actual = encoderRead()
    alt = altEncoderRead()
    err = goal - actual
    if count <= 0 then
      print(format("%8.4f\t%8.4f\t%8.4f", actual, alt, 100*mbRead(2, 3)-50))
        count = 40
    end
    count = count - 1
    mbWrite(46004, 3, actual)
--    mbWrite(46006, 3, err)
    mbWrite(46006, 3, actual - alt)
    mbWrite(46008, 3, alt)

    -- If new command
    if cmd == 1 then --> Halt motor
      state = states.halt
      dir = halt()

    elseif cmd == 2 then  --> Move to goal
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
    
    -- Motion state machine  
    mbWrite(46181, 0, state)       -- Record current state in user MB register.
    --print(format("actual: %.3f, goal = %.3f", actual, goal))
    if state > 0 then
      drive = mbRead(2014) + 2 * mbRead(2015)
--      print(string.format("%.3f\t%.3f\t%d\t%.3f\t%d\t%s", t, err, state, actual, drive, dir))
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
--  print(format("%d, %.3f", nAvg2, 0.000025 * (getTick() - lastTick)))
    collectgarbage("collect")
  end
end
