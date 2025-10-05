from __future__ import annotations

from textwrap import dedent
from string import Template


def generate_loader(blob_filename: str, role: str, license_key_hint: str | None = None, salt: str = "fivem-locker") -> str:
    lua = """
    local role = '$role'

    local function read_blob(path)
      local f = assert(io.open(path, 'rb'))
      local d = f:read('*a')
      f:close()
      return d
    end

    local function get_license()
      local k = GetConvar('locker_license', '')
      if k == nil or k == '' then
        k = os.getenv('LOCKER_LICENSE') or ''
      end
      if k == '' then
        error('License key missing. Set convar locker_license or env LOCKER_LICENSE')
      end
      return k
    end

    local function split_tag(data)
      return string.sub(data,1,4), string.sub(data,5,16), string.sub(data,17)
    end

    local function decrypt(data)
      local tag, nonce, rest = split_tag(data)
      local lic = get_license()
      local salt = '$salt'
      if tag == 'XRF\0' then
        local seed = 2166136261
        local function fnv1a32_step(c)
          seed = bit.bxor(seed, c) & 0xffffffff
          seed = (seed * 16777619) & 0xffffffff
        end
        local mix = lic .. '|' .. salt .. nonce
        for i=1,#mix do
          fnv1a32_step(string.byte(mix, i))
        end
        local function xorshift32(x)
          x = bit.bxor(x, bit.lshift(x, 13))
          x = bit.bxor(x, bit.rshift(x, 17))
          x = bit.bxor(x, bit.lshift(x, 5))
          return x & 0xffffffff
        end
        local out = {}
        local x = seed
        for i=1,#rest do
          x = xorshift32(x)
          local b = bit.band(x, 0xff)
          local rb = string.byte(rest, i)
          out[i] = string.char(bit.bxor(rb, b))
        end
        return table.concat(out)
      else
        error('Unknown blob tag')
      end
    end

    local function split_meta(payload)
      local sep = "\n\n--[[META_SPLIT]]\n\n"
      local i = string.find(payload, sep, 1, true)
      if not i then error('Malformed payload') end
      local meta = string.sub(payload, 1, i-1)
      local body = string.sub(payload, i + #sep)
      return meta, body
    end

    local function explode_bundle(body)
      local sep = "\n\n--[[BUNDLE_SPLIT]]\n\n"
      local parts = {}
      local idx = 1
      while true do
        local j = string.find(body, sep, idx, true)
        if not j then
          table.insert(parts, string.sub(body, idx))
          break
        end
        table.insert(parts, string.sub(body, idx, j-1))
        idx = j + #sep
      end
      return parts
    end

    local function run_bundle(meta_json, parts)
      for _, code in ipairs(parts) do
        local fn, err = load(code)
        if not fn then error('load error: ' .. tostring(err)) end
        fn()
      end
    end

    local function main()
      local resPath = GetResourcePath(GetCurrentResourceName())
      if not resPath then error('Cannot resolve resource path') end
      local blobPath = resPath .. '/$blob_filename'
      local blob = read_blob(blobPath)
      local dec = decrypt(blob)
      local meta, body = split_meta(dec)
      local parts = explode_bundle(body)
      run_bundle(meta, parts)
    end

    main()
    """
    return dedent(Template(lua).substitute(role=role, blob_filename=blob_filename, salt=salt)).strip() + "\n"