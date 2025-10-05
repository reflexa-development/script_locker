-- FiveM locker loader (generated)
-- side: __SIDE__

local RESOURCE = GetCurrentResourceName()
local BUNDLE_FILE = __BUNDLE_FILENAME__
local KEY = __KEY_LITERAL__ -- Embedded passphrase; obfuscation only, not true security.

-- base64 decode (ASCII-only)
local function b64_decode(data)
  local b='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  data = data:gsub('[^'..b..'=]', '')
  return (data:gsub('.', function(x)
    if (x == '=') then return '' end
    local r,f='',(b:find(x)-1)
    for i=6,1,-1 do r=r..(f%2^i - f%2^(i-1) > 0 and '1' or '0') end
    return r
  end):gsub('%d%d%d?%d?%d?%d?%d?%d?', function(x)
    if (#x ~= 8) then return '' end
    local c=0
    for i=1,8 do c=c + (x:sub(i,i)=='1' and 2^(8-i) or 0) end
    return string.char(c)
  end))
end

-- FNV-1a 32-bit
local function fnv1a32(bytes, seed)
  local FNV_OFFSET = 0x811C9DC5
  local FNV_PRIME = 0x01000193
  local value = seed or FNV_OFFSET
  for i = 1, #bytes do
    value = value ~ string.byte(bytes, i)
    value = (value * FNV_PRIME) & 0xFFFFFFFF
  end
  return value & 0xFFFFFFFF
end

-- xorshift32
local function xorshift32(x)
  x = x ~ ((x << 13) & 0xFFFFFFFF)
  x = x ~ (x >> 17)
  x = x ~ ((x << 5) & 0xFFFFFFFF)
  return x & 0xFFFFFFFF
end

local function keystream(len, seed)
  local out = {}
  local state = seed & 0xFFFFFFFF
  for i = 1, len do
    state = xorshift32(state)
    out[i] = string.char(state & 0xFF)
  end
  return table.concat(out)
end

local function decrypt_xor_stream(blob, key, side_tag)
  if #blob < 8 then error('bundle blob too small') end
  local salt = string.sub(blob, 1, 8)
  local ciphertext = string.sub(blob, 9)
  local seed_material = key .. salt .. side_tag
  local seed = fnv1a32(seed_material, nil)
  local ks = keystream(#ciphertext, seed)
  local out = {}
  for i = 1, #ciphertext do
    local b = string.byte(ciphertext, i) ~ string.byte(ks, i)
    out[i] = string.char(b)
  end
  return table.concat(out)
end

-- Parse bundle blob of format:
--   header: "FLOK1\n"
--   N:<num>\n
--   For each entry:
--     P:<path_len>\n
--     <path_bytes>
--     C:<code_len>\n
--     <code_bytes>
local function parse_bundle(plain)
  local pos = 1
  local function read_line()
    local s, e = string.find(plain, '\n', pos, true)
    if not s then error('malformed bundle (no newline)') end
    local line = string.sub(plain, pos, s-1)
    pos = e + 1
    return line
  end
  local function read_bytes(n)
    local s = string.sub(plain, pos, pos + n - 1)
    if #s ~= n then error('malformed bundle (short read)') end
    pos = pos + n
    return s
  end
  -- header
  local header = read_line()
  if header ~= 'FLOK1' then error('bad bundle header') end
  local n_line = read_line()
  local n = tonumber(string.match(n_line, '^N:(%d+)$'))
  if not n then error('bad bundle count') end
  local entries = {}
  for _ = 1, n do
    local p_line = read_line()
    local p_len = tonumber(string.match(p_line, '^P:(%d+)$'))
    if not p_len then error('bad path len') end
    local path = read_bytes(p_len)
    local c_line = read_line()
    local c_len = tonumber(string.match(c_line, '^C:(%d+)$'))
    if not c_len then error('bad code len') end
    local code = read_bytes(c_len)
    entries[#entries+1] = { path = path, code = code }
  end
  return entries
end

local function load_and_run(entries)
  local env = _G -- run in global env; sandboxing optional
  for i = 1, #entries do
    local e = entries[i]
    local chunk, err = load(e.code, '@' .. e.path, 'bt', env)
    if not chunk then error('load error for '..e.path..': '..tostring(err)) end
    local ok, run_err = pcall(chunk)
    if not ok then error('runtime error for '..e.path..': '..tostring(run_err)) end
  end
end

Citizen.CreateThread(function()
  local side_tag = '__SIDE__'
  local data = LoadResourceFile(RESOURCE, BUNDLE_FILE)
  if not data or #data == 0 then error('Bundle file missing: '..tostring(BUNDLE_FILE)) end
  local encrypted = b64_decode(data)
  local plain = decrypt_xor_stream(encrypted, KEY, side_tag)
  local entries = parse_bundle(plain)
  load_and_run(entries)
end)
