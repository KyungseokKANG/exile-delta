-- Exile Delta: PoB(Path of Building Community) headless bootstrap.
-- Based on PoB's src/HeadlessWrapper.lua. Runs inside lupa's LuaJIT.
-- Python sets before loading: _ES_SRC, _ES_USER, _ES_INFLATE(data), _ES_DEFLATE(data), _ES_LOG(msg), _ES_TIME()

local callbackTable = { }
local mainObject
function runCallback(name, ...)
	if callbackTable[name] then
		return callbackTable[name](...)
	elseif mainObject and mainObject[name] then
		return mainObject[name](mainObject, ...)
	end
end
function SetCallback(name, func) callbackTable[name] = func end
function GetCallback(name) return callbackTable[name] end
function SetMainObject(obj) mainObject = obj end

local imageHandleClass = { }
imageHandleClass.__index = imageHandleClass
function NewImageHandle() return setmetatable({ }, imageHandleClass) end
function imageHandleClass:Load(fileName, ...) self.valid = true end
function imageHandleClass:Unload() self.valid = false end
function imageHandleClass:IsValid() return self.valid end
function imageHandleClass:SetLoadingPriority(pri) end
function imageHandleClass:ImageSize() return 1, 1 end

function RenderInit(flag, ...) end
function GetScreenSize() return 1920, 1080 end
function GetScreenScale() return 1 end
function GetVirtualScreenSize() return GetScreenSize() end
function GetDPIScaleOverridePercent() return 1 end
function SetDPIScaleOverridePercent(scale) end
function SetClearColor(r, g, b, a) end
function SetDrawLayer(layer, subLayer) end
function SetViewport(x, y, width, height) end
function SetDrawColor(r, g, b, a) end
function DrawImage(...) end
function DrawImageQuad(...) end
function DrawString(...) end
function DrawStringWidth(height, font, text) return 1 end
function DrawStringCursorIndex(height, font, text, cursorX, cursorY) return 0 end
function StripEscapes(text) return text:gsub("%^%d",""):gsub("%^x%x%x%x%x%x%x","") end
function GetAsyncCount() return 0 end
function NewFileSearch() end
function SetWindowTitle(title) end
function GetCursorPos() return 0, 0 end
function SetCursorPos(x, y) end
function ShowCursor(doShow) end
function IsKeyDown(keyName) end
function Copy(text) end
function Paste() end
function Deflate(data) return _ES_DEFLATE(data) end
function Inflate(data) return _ES_INFLATE(data) end
function GetTime() return _ES_TIME() end
function GetScriptPath() return _ES_SRC end
function GetRuntimePath() return _ES_SRC end
function GetUserPath() return _ES_USER end
function MakeDir(path) end
function RemoveDir(path) end
function SetWorkDir(path) end
function GetWorkDir() return _ES_SRC end
function LaunchSubScript(scriptText, funcList, subList, ...) end
function AbortSubScript(ssID) end
function IsSubScriptRunning(ssID) end
function LoadModule(fileName, ...)
	if not fileName:match("%.lua") then fileName = fileName .. ".lua" end
	local func, err = loadfile(fileName)
	if func then return func(...) end
	error("LoadModule() error loading '"..fileName.."': "..tostring(err))
end
function PLoadModule(fileName, ...)
	if not fileName:match("%.lua") then fileName = fileName .. ".lua" end
	local func, err = loadfile(fileName)
	if func then return PCall(func, ...) end
	error("PLoadModule() error loading '"..fileName.."': "..tostring(err))
end
function PCall(func, ...)
	local ret = { pcall(func, ...) }
	if ret[1] then
		table.remove(ret, 1)
		return nil, unpack(ret)
	else
		return ret[2]
	end
end
function ConPrintf(fmt, ...) _ES_LOG(string.format(fmt, ...)) end
function ConPrintTable(tbl, noRecurse) end
function ConExecute(cmd) end
function ConClear() end
function SpawnProcess(cmdName, args) end
function OpenURL(url) end
function SetProfiling(isEnabled) end
function Restart() end
function Exit() end
function TakeScreenshot() end
function GetCloudProvider(fullPath) return nil, nil, nil end
print = function(...)
	local t = { }
	for i = 1, select("#", ...) do t[#t + 1] = tostring(select(i, ...)) end
	_ES_LOG(table.concat(t, "\t"))
end

-- lua-utf8 (C module) replacement: PoB only needs it for number formatting / text edit (ASCII ok)
package.preload["lua-utf8"] = function()
	return {
		reverse = string.reverse, gsub = string.gsub, find = string.find, sub = string.sub,
		match = string.match, len = string.len, char = string.char, byte = string.byte,
		lower = string.lower, upper = string.upper, gmatch = string.gmatch,
		next = function(s, i) i = (i or 0) + 1; if i <= #s then return i end end,
	}
end
local l_require = require
function require(name)
	if name == "lcurl.safe" or name == "lua-profiler" then return nil end
	return l_require(name)
end

arg = arg or { }
dofile("Launch.lua")
mainObject.continuousIntegrationMode = false
runCallback("OnInit")
runCallback("OnFrame")
if mainObject.promptMsg then
	error("PoB startup failed: " .. tostring(mainObject.promptMsg))
end
build = mainObject.main.modes["BUILD"]

-------------------------------------------------------------------------------
-- Exile Delta API (es_*)
-------------------------------------------------------------------------------
local STAT_KEYS = {
	"FullDPS", "CombinedDPS", "TotalDPS", "TotalDot", "WithBleedDPS", "WithIgniteDPS", "WithPoisonDPS",
	"AverageHit", "Speed", "CritChance", "CritMultiplier", "HitChance",
	"TotalEHP", "Life", "LifeUnreserved", "EnergyShield", "Mana", "ManaUnreserved", "Ward",
	"Armour", "Evasion", "PhysicalDamageReduction", "EffectiveSpellSuppressionChance",
	"EffectiveBlockChance", "EffectiveSpellBlockChance", "MeleeEvadeChance",
	"FireResist", "ColdResist", "LightningResist", "ChaosResist",
	"PhysicalMaximumHitTaken", "FireMaximumHitTaken", "ColdMaximumHitTaken",
	"LightningMaximumHitTaken", "ChaosMaximumHitTaken",
	"LifeRegenRecovery", "Str", "Dex", "Int", "MovementSpeedMod",
	"FireResistOverCap", "ColdResistOverCap", "LightningResistOverCap", "ChaosResistOverCap",
	"MissingFireResist", "MissingColdResist", "MissingLightningResist", "MissingChaosResist",
	"ReqStr", "ReqDex", "ReqInt",
	-- 스스로 받는 지속 피해(RF 등)와 회복: PoB 사이드바 Total Degen / Net Life · ES · Mana Recovery / Total Net Recovery
	-- (Net* 는 지속 피해가 있을 때만 PoB 가 계산. 피해는 보호막 재생이 있으면 보호막, 없으면 생명력이 받음)
	"TotalBuildDegen", "NetEnergyShieldRegen", "NetManaRegen", "TotalNetRegen",
	"EnergyShieldRegenRecovery", "ManaRegenRecovery",
}

-- 소환수를 부르는 주 스킬(면죄 · 지배의 일격 · 좀비 등): 소환수 DPS 를 '주 스킬 DPS'(CombinedDPS)에 더할지
-- (PoB Full DPS 는 원래 소환수 DPS 를 포함. Python 쪽 설정 minion_in_main 으로 켜고 끔)
es_minion_in_main = true

local function minionDPS(output)
	local mo = output and output.Minion
	local v = mo and (mo.CombinedDPS or mo.TotalDPS)
	if type(v) == "number" and v == v and v > 0 and v < math.huge then return v end
	return nil
end

-- CombinedDPS 를 소환수 포함으로 바꾸고, 플레이어 몫(PlayerDPS) · 소환수 몫(MinionDPS) 을 따로 남김
local function addMinion(t, output)
	local md = minionDPS(output)
	if not md then return end
	t.MinionDPS = md
	t.PlayerDPS = t.CombinedDPS or 0
	if es_minion_in_main then t.CombinedDPS = (t.CombinedDPS or 0) + md end
end

function es_set_minion_in_main(on)
	es_minion_in_main = on and true or false
	return es_summary()
end

local function pickStats(output)
	local t = { }
	if not output then return t end
	for _, k in ipairs(STAT_KEYS) do
		local v = output[k]
		if type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
			t[k] = v
		elseif v == math.huge then
			t[k] = 1e300
		end
	end
	addMinion(t, output)
	-- RF 처럼 스스로 받는 지속 피해(초당)와 그걸 뺀 순 생명력 재생 (PoB Calcs 의 Net Life Regen)
	local degen = 0
	for _, dt in ipairs({ "Physical", "Fire", "Cold", "Lightning", "Chaos" }) do
		local v = output[dt .. "BuildDegen"]
		if type(v) == "number" and v == v and v < math.huge then degen = degen + v end
	end
	t.LifeDegen = degen
	if degen > 0 and type(output.NetLifeRegen) == "number" then
		t.NetLifeRegen = output.NetLifeRegen
	else
		t.NetLifeRegen = t.LifeRegenRecovery
	end
	return t
end

local function frame() runCallback("OnFrame") end

function es_new()
	mainObject.main:SetMode("BUILD", false, "")
	frame()
	build = mainObject.main.modes["BUILD"]
end

-- 바알 젬(바알 면죄 등)은 스킬이 둘(바알 쪽 · 일반 쪽). 계정에서 가져오면 PoB 가 바알 쪽만 켜서(enableGlobal2 없음)
-- 실제로 피해를 주는 일반 쪽이 Full DPS 에서 빠짐 → 가져온 빌드에선 둘 다 켬 (PoB 에서 젬을 직접 넣을 때와 같음)
local function enableVaalSecondary()
	local changed = false
	for _, g in ipairs(build.skillsTab.socketGroupList) do
		for _, gem in ipairs(g.gemList or { }) do
			if gem.gemData and gem.gemData.vaalGem and gem.enableGlobal2 == nil then
				gem.enableGlobal2 = true
				changed = true
			end
		end
		if changed then build.skillsTab:ProcessSocketGroup(g) end
	end
	if changed then
		build.modFlag = true
		build.buildFlag = true
		frame()
	end
end

local function mainDPS()
	local o = build.calcsTab.mainOutput or { }
	return (o.CombinedDPS or 0) + (es_minion_in_main and minionDPS(o) or 0)
end

-- 주 그룹에서 고른 액티브 스킬이 DPS 0 (예: 바알 면죄는 파수꾼을 승천시킬 뿐) 이고 같은 그룹에 다른 액티브가
-- 있으면 DPS 가 가장 높은 쪽으로 (PoB 사이드바 두 번째 드롭다운)
local function fixMainActive()
	local g = build.skillsTab.socketGroupList[build.mainSocketGroup]
	if not g or not g.displaySkillList or #g.displaySkillList < 2 or mainDPS() > 0 then return end
	local cur = g.mainActiveSkill or 1
	local best, bestI = 0, cur
	for i = 1, #g.displaySkillList do
		g.mainActiveSkill = i
		build.modFlag = true
		build.buildFlag = true
		frame()
		local d = mainDPS()
		if d > best then best, bestI = d, i end
	end
	g.mainActiveSkill = bestI
	build.modFlag = true
	build.buildFlag = true
	frame()
end

function es_load_xml(xmlText, name)
	-- 예전에 가져와 저장된 빌드: 바알 젬 일반 쪽이 enableGlobal2="nil" 로 저장돼 있음 → 켬
	xmlText = xmlText:gsub('enableGlobal2="nil"', 'enableGlobal2="true"')
	mainObject.main:SetMode("BUILD", false, name or "", xmlText)
	frame()
	build = mainObject.main.modes["BUILD"]
	pcall(fixMainActive)
	return build.buildFlag ~= nil
end

-- characterJSON: official API style { character = { equipment, passives, jewels, ... } }
-- or legacy pair (items + passives) already merged into that shape by Python.
-------------------------------------------------------------------------------
-- 다시 가져오기 때 사용자가 고른 것 유지: Full DPS·그룹/젬 사용·주 스킬·스킬 파트·계산 설정·플라스크 사용
-- (장비·트리·젬 레벨은 게임 것을 그대로). 소켓 그룹은 '장착 칸 + 젬 이름'으로, 없으면 '젬 이름'만으로 짝지음.
-------------------------------------------------------------------------------
local function gemName(gem)
	return gem.nameSpec or (gem.grantedEffect and gem.grantedEffect.name) or ""
end

local function groupKeys(g)
	local names = { }
	for _, gem in ipairs(g.gemList or { }) do names[#names + 1] = gemName(gem) end
	local n = table.concat(names, ",")
	return (g.slot or "") .. "|" .. n, n
end

local function copyTable(t)
	local o = { }
	for k, v in pairs(t or { }) do o[k] = type(v) == "table" and copyTable(v) or v end
	return o
end

function es_get_prefs()
	local p = { groups = { }, config = { }, flasks = { } }
	for gi, g in ipairs(build.skillsTab.socketGroupList) do
		local full, names = groupKeys(g)
		local gems = { }
		for _, gem in ipairs(g.gemList or { }) do
			gems[gemName(gem)] = { enabled = gem.enabled ~= false, skillPart = gem.skillPart,
			                       skillMinion = gem.skillMinion, skillMinionSkill = gem.skillMinionSkill }
		end
		p.groups[#p.groups + 1] = { full = full, names = names, slot = g.slot or "", enabled = g.enabled ~= false,
		                            includeInFullDPS = g.includeInFullDPS and true or false,
		                            mainActiveSkill = g.mainActiveSkill, gems = gems, main = (gi == build.mainSocketGroup) }
	end
	local ct = build.configTab
	p.config = copyTable(ct.configSets[ct.activeConfigSetId].input)
	for i = 1, 5 do
		local s = build.itemsTab.slots["Flask " .. i]
		if s then p.flasks["Flask " .. i] = s.active and true or false end
	end
	return p
end

function es_apply_prefs(p)
	if not p then return end
	local used = { }
	local function find(g)
		local full, names = groupKeys(g)
		for i, pg in ipairs(p.groups) do
			if not used[i] and pg.full == full then used[i] = true return pg end
		end
		for i, pg in ipairs(p.groups) do
			if not used[i] and pg.names == names and names ~= "" then used[i] = true return pg end
		end
		-- 같은 장착 칸에서 액티브 젬이 같은 그룹 (서포트를 더 꽂거나 뺀 경우)
		for i, pg in ipairs(p.groups) do
			if not used[i] and pg.slot == (g.slot or "") then
				for _, gem in ipairs(g.gemList or { }) do
					local pv = pg.gems[gemName(gem)]
					if pv and not (gem.grantedEffect and gem.grantedEffect.support) then used[i] = true return pg end
				end
			end
		end
	end
	for gi, g in ipairs(build.skillsTab.socketGroupList) do
		local pg = find(g)
		if pg then
			g.enabled = pg.enabled
			g.includeInFullDPS = pg.includeInFullDPS
			if pg.mainActiveSkill then g.mainActiveSkill = pg.mainActiveSkill end
			for _, gem in ipairs(g.gemList or { }) do
				local pv = pg.gems[gemName(gem)]
				if pv then
					gem.enabled = pv.enabled
					gem.skillPart = pv.skillPart
					gem.skillMinion = pv.skillMinion
					gem.skillMinionSkill = pv.skillMinionSkill
				end
			end
			if pg.main then build.mainSocketGroup = gi end
			build.skillsTab:ProcessSocketGroup(g)
		end
	end
	local ct = build.configTab
	local input = ct.configSets[ct.activeConfigSetId].input
	for k in pairs(input) do input[k] = nil end
	for k, v in pairs(p.config) do input[k] = v end
	if ct.UpdateControls then ct:UpdateControls() end
	ct:BuildModList()
	for name, active in pairs(p.flasks) do
		local s = build.itemsTab.slots[name]
		if s and build.itemsTab.activeItemSet[name] then
			s.active = active
			if s.controls and s.controls.activate then s.controls.activate.state = active end
			build.itemsTab.activeItemSet[name].active = active
		end
	end
	build.modFlag = true
	build.buildFlag = true
	frame()
end

function es_load_character_json(json, prevXml)
	local prefs
	if prevXml and #prevXml > 0 then
		local ok, r = pcall(function() es_load_xml(prevXml, "") return es_get_prefs() end)
		if ok then prefs = r else _ES_LOG("prefs: " .. tostring(r)) end
	end
	es_load_character_json_raw(json)
	if prefs then
		local ok, e = pcall(es_apply_prefs, prefs)
		if not ok then _ES_LOG("apply prefs: " .. tostring(e)) end
	end
	pcall(fixMainActive)
	return true
end

function es_load_character_json_raw(json)
	es_new()
	local dkjson = require "dkjson"
	local input = dkjson.decode(json)
	local char = input.character or input
	build.importTab:ImportPassiveTreeAndJewels(char, true)
	frame()
	build.importTab:ImportItemsAndSkills(char, true, true, false)
	frame()
	pcall(enableVaalSecondary)
	-- PoB 와 동일: 주 스킬은 PoB 의 GuessMainSocketGroup(젬이 가장 많은 그룹), Full DPS 포함은 비움
	return true
end

-- If no socket group is flagged for Full DPS, include the main group so FullDPS is meaningful.
function es_ensure_full_dps()
	for _, group in ipairs(build.skillsTab.socketGroupList) do
		if group.includeInFullDPS then return end
	end
	local group = build.skillsTab.socketGroupList[build.mainSocketGroup]
	if group then
		group.includeInFullDPS = true
		build.modFlag = true
		build.buildFlag = true
		frame()
	end
end

function es_pick_best_main_skill()
	local best, bestIdx = -1, build.mainSocketGroup
	for i, group in ipairs(build.skillsTab.socketGroupList) do
		if group.enabled and group.displaySkillList and #group.displaySkillList > 0 then
			build.mainSocketGroup = i
			build.modFlag = true
			build.buildFlag = true
			frame()
			local o = build.calcsTab.mainOutput
			local dps = (o.CombinedDPS or 0) + (es_minion_in_main and minionDPS(o) or 0)
			if dps > best then best, bestIdx = dps, i end
		end
	end
	build.mainSocketGroup = bestIdx
	build.modFlag = true
	build.buildFlag = true
	frame()
end

function es_save_xml()
	return build:SaveDB("code")
end

function es_summary()
	local out = { }
	out.className = build.spec.curClassName
	out.ascendClassName = build.spec.curAscendClassName
	out.level = build.characterLevel
	out.mainSocketGroup = build.mainSocketGroup
	out.stats = pickStats(build.calcsTab.mainOutput)
	local mainSkill = build.calcsTab.mainEnv and build.calcsTab.mainEnv.player and build.calcsTab.mainEnv.player.mainSkill
	out.mainSkillName = mainSkill and mainSkill.activeEffect and mainSkill.activeEffect.grantedEffect.name or ""
	-- (바알 젬의 일반 쪽은 계산 단계에서 이름이 변형 젬 이름으로 나올 때가 있어 드롭다운 목록 이름을 우선)
	local mg = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local ds = mg and mg.displaySkillList and mg.displaySkillList[mg.mainActiveSkill or 1]
	if ds and ds.activeEffect and ds.activeEffect.grantedEffect and ds.activeEffect.grantedEffect.name then
		out.mainSkillName = ds.activeEffect.grantedEffect.name
	end
	local menv = build.calcsTab.mainEnv
	out.minionName = menv and menv.minion and menv.minion.minionData and menv.minion.minionData.name or nil
	out.minionInMain = es_minion_in_main
	out.groups = { }
	for i, group in ipairs(build.skillsTab.socketGroupList) do
		local gems = { }
		for _, gem in ipairs(group.gemList or { }) do
			local gname = gem.nameSpec
			if not gname or gname == "" then
				gname = (gem.grantedEffect and gem.grantedEffect.name) or (gem.gemData and gem.gemData.name) or "?"
			end
			gems[#gems + 1] = {
				name = gname,
				level = gem.level, quality = gem.quality, enabled = gem.enabled ~= false,
				maxLevel = gem.gemData and gem.gemData.naturalMaxLevel or nil,
				fromItem = gem.fromItem or nil,
				support = gem.gemData and gem.gemData.grantedEffect and gem.gemData.grantedEffect.support or false,
			}
		end
		local actives = { }
		for j, s in ipairs(group.displaySkillList or { }) do
			local ge = s.activeEffect and s.activeEffect.grantedEffect
			actives[j] = ge and ge.name or ("Skill " .. j)
		end
		out.groups[i] = {
			label = group.displayLabel or group.label or "",
			slot = group.slot or "",
			enabled = group.enabled ~= false,
			includeInFullDPS = group.includeInFullDPS == true,
			mainActiveSkill = group.mainActiveSkill or 1,
			actives = actives,
			gems = gems,
		}
	end
	-- 주 스킬의 파트(예: "All Projectiles") 목록과 선택값
	out.skillParts = { }
	out.skillPart = 0
	local mg = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local ms = mg and mg.displaySkillList and mg.displaySkillList[mg.mainActiveSkill or 1]
	if ms and ms.activeEffect and ms.activeEffect.grantedEffect.parts then
		for j, p in ipairs(ms.activeEffect.grantedEffect.parts) do out.skillParts[j] = p.name or ("Part " .. j) end
		out.skillPart = (ms.activeEffect.srcInstance and ms.activeEffect.srcInstance.skillPart) or 1
	end
	-- 바알 면죄 · 바알 지배: '바알 쪽 = 승천한 파수꾼' 으로 보여주기 위한 정보 (아래쪽에 정의된 전역 함수)
	if es_ascend_info then
		local ok, a = pcall(es_ascend_info)
		if ok then out.ascend = a end
	end
	-- 소환수 / 소환수 스킬 (PoB 사이드바 Minion · Minion skill 드롭다운과 같은 목록)
	out.minions = { }
	out.minionSel = 0
	out.minionSkills = { }
	out.minionSkillSel = 0
	if ms and ms.activeEffect and ms.skillFlags and not ms.skillFlags.disable
		and (ms.activeEffect.grantedEffect.minionList or (ms.minionList and ms.minionList[1])) then
		local src = ms.activeEffect.srcInstance or { }
		if not ms.activeEffect.grantedEffect.minionHasItemSet then
			for j, id in ipairs(ms.minionList or { }) do
				out.minions[j] = data.minions[id] and data.minions[id].name or id
				if id == src.skillMinion then out.minionSel = j end
			end
			if out.minionSel == 0 and #out.minions > 0 then out.minionSel = 1 end
		end
		if ms.minion and ms.minion.activeSkillList then
			for j, sk in ipairs(ms.minion.activeSkillList) do
				out.minionSkills[j] = sk.activeEffect.grantedEffect.name
			end
			out.minionSkillSel = src.skillMinionSkill or 1
		end
	end
	out.pobVersion = mainObject.versionNumber or "?"
	-- 플라스크 활성 여부 (PoB Items 탭의 체크박스)
	out.flasks = { }
	for n = 1, 5 do
		local slot = build.itemsTab.slots["Flask " .. n]
		local item = slot and build.itemsTab.items[slot.selItemId]
		if item then
			out.flasks[#out.flasks + 1] = { slot = "Flask " .. n, name = item.name, active = slot.active == true }
		end
	end
	out.config = es_get_config()
	out.skillDPS = { }
	for i, s in ipairs(build.calcsTab.mainOutput.SkillDPS or { }) do
		out.skillDPS[i] = { name = s.name, dps = s.dps, count = s.count, trigger = s.trigger }
	end
	out.items = { }
	for slotName, slot in pairs(build.itemsTab.slots) do
		local item = build.itemsTab.items[slot.selItemId]
		if item and not slot.inactive then
			out.items[slotName] = { name = item.name, rarity = item.rarity, base = item.baseName }
		end
	end
	return out
end

-------------------------------------------------------------------------------
-- Configuration 탭
-------------------------------------------------------------------------------
local configVarList = LoadModule("Modules/ConfigOptions")
local configVarByName = { }
for _, v in ipairs(configVarList) do
	if v.var then configVarByName[v.var] = v end
end
-- 편집 대상에서 제외하는 섹션: 적 기준은 PoB 기본값 그대로, 사용자 정의 모드는 텍스트라 제외
local LOCKED_SECTIONS = { ["Enemy Stats"] = true, ["Custom Modifiers"] = true }
local configVarSection = { }
do
	local sec
	for _, v in ipairs(configVarList) do
		if v.section then sec = v.section elseif v.var then configVarSection[v.var] = sec end
	end
end

local function cleanLabel(s)
	s = StripEscapes(tostring(s or ""))
	return (s:gsub("%s*:%s*$", ""))
end

local function valueText(varData, v)
	if varData.type == "list" then
		for _, o in ipairs(varData.list or { }) do
			if o.val == v then return cleanLabel(o.label) end
		end
	elseif varData.type == "check" then
		return v and "예" or "아니오"
	end
	return tostring(v)
end

-- PoB Configuration 탭과 같은 구성: 섹션별로, PoB 가 현재 빌드에서 보여주는 항목만 (shown 판정은 PoB 자체 로직)
function es_get_config()
	local ct = build.configTab
	local input = ct.configSets[ct.activeConfigSetId].input
	local placeholder = ct.configSets[ct.activeConfigSetId].placeholder
	local res = { sections = { }, locked = { } }
	local secIdx, j, cur = 0, 0, nil
	for _, vd in ipairs(configVarList) do
		if vd.section then
			secIdx = secIdx + 1
			j = 0
			cur = { name = vd.section, col = vd.col, items = { } }
			if not LOCKED_SECTIONS[vd.section] then res.sections[#res.sections + 1] = cur end
		elseif cur then
			j = j + 1
			local section = ct.sectionList[secIdx]
			local control = section and section.varControlList and section.varControlList[j]
			local ok, shown = pcall(function() return control and control:GetProperty("shown") end)
			shown = ok and shown and true or false
			local v = vd.var and input[vd.var]
			local def = vd.var and ct:GetDefaultState(vd.var, type(v))
			local changed = vd.var and v ~= nil and v ~= def and not (v == false and def == nil)
			if LOCKED_SECTIONS[cur.name] then
				if changed and vd.type ~= "text" then
					res.locked[#res.locked + 1] = { label = cleanLabel(vd.label), value = valueText(vd, v) }
				end
			elseif shown or changed then
				local item = { label = cleanLabel(vd.label), shown = shown,
					parent = type(vd.ifOption) == "string" and vd.ifOption or nil }
				if vd.tooltip and type(vd.tooltip) == "string" then item.tooltip = StripEscapes(vd.tooltip) end
				if vd.var and vd.type ~= "text" then
					item.var = vd.var
					item.type = vd.type
					item.value = v
					item.default = def
					item.changed = changed
					item.placeholder = placeholder[vd.var]
					if vd.type == "list" then
						item.list = { }
						for k, o in ipairs(vd.list or { }) do item.list[k] = { val = o.val, label = cleanLabel(o.label) } end
					end
				elseif not vd.var then
					item.type = "label"
				end
				if item.type then cur.items[#cur.items + 1] = item end
			end
		end
	end
	-- 비어 있는 소제목(label) 정리: 뒤에 옵션이 없는 label 은 제거
	for _, sec in ipairs(res.sections) do
		local out = { }
		for k, it in ipairs(sec.items) do
			local nxt = sec.items[k + 1]
			if it.type ~= "label" or (nxt and nxt.type ~= "label") then out[#out + 1] = it end
		end
		sec.items = out
	end
	return res
end

function es_set_config(var, value)
	local ct = build.configTab
	ct.configSets[ct.activeConfigSetId].input[var] = value
	if ct.UpdateControls then ct:UpdateControls() end
	ct:BuildModList()
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

function es_reset_config()
	local ct = build.configTab
	local input = ct.configSets[ct.activeConfigSetId].input
	for k in pairs(input) do
		if not LOCKED_SECTIONS[configVarSection[k] or ""] then input[k] = nil end
	end
	for _, vd in ipairs(configVarList) do
		if vd.var and not LOCKED_SECTIONS[configVarSection[vd.var] or ""] then
			input[vd.var] = vd.defaultState
			if vd.defaultIndex then input[vd.var] = vd.list[vd.defaultIndex].val end
		end
	end
	if ct.UpdateControls then ct:UpdateControls() end
	ct:BuildModList()
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

function es_set_flask(slotName, active)
	local slot = build.itemsTab.slots[slotName]
	if not slot then return false end
	slot.active = active and true or false
	if slot.controls and slot.controls.activate then slot.controls.activate.state = slot.active end
	build.itemsTab.activeItemSet[slotName].active = slot.active
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

function es_set_active_skill(groupIndex, activeIndex)
	local group = build.skillsTab.socketGroupList[groupIndex]
	if not group then return false end
	group.mainActiveSkill = activeIndex
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

function es_set_skill_part(part)
	local group = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local s = group and group.displaySkillList and group.displaySkillList[group.mainActiveSkill or 1]
	if not (s and s.activeEffect and s.activeEffect.srcInstance) then return false end
	s.activeEffect.srcInstance.skillPart = part
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

-- 주 스킬의 소환수 / 소환수 스킬 선택 (PoB 사이드바와 같은 값: srcInstance.skillMinion / skillMinionSkill)
local function mainSrc()
	local g = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local ms = g and g.displaySkillList and g.displaySkillList[g.mainActiveSkill or 1]
	return ms, ms and ms.activeEffect and ms.activeEffect.srcInstance
end

-- 바알 면죄 · 바알 지배: 바알 쪽은 PoB 에서 피해 0 (파수꾼 승천만), 승천한 파수꾼은 일반 쪽 소환수 목록에 있음.
-- → 앱에서는 '바알 면죄' = 일반 면죄 + 승천한 파수꾼, '면죄' = 일반 면죄 + 일반 파수꾼 으로 보여줌.
-- 반환: { vaal = 바알 쪽 순번, normal = 일반 쪽 순번, asc = 승천 소환수 id, base = 일반 소환수 id } 또는 nil
local function ascendPair(g)
	if not g or not g.displaySkillList then return nil end
	local vaalI, normI, ascId, baseId
	for i, sk in ipairs(g.displaySkillList) do
		local ge = sk.activeEffect and sk.activeEffect.grantedEffect
		if ge then
			local asc, base
			for _, id in ipairs(sk.minionList or { }) do
				local m = data.minions[id]
				if m and m.name:match("^Ascended ") then asc = id elseif not base then base = id end
			end
			if asc and base then
				normI, ascId, baseId = i, asc, base
			elseif ge.skillTypes and ge.skillTypes[SkillType.Vaal] and not ge.minionList then
				vaalI = i
			end
		end
	end
	if vaalI and normI then return { vaal = vaalI, normal = normI, asc = ascId, base = baseId } end
	return nil
end

-- es_summary 에서 부름: { vaal, normal, on = 지금 승천 파수꾼인지 }
function es_ascend_info()
	local g = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local p = ascendPair(g)
	if not p then return nil end
	local src = g.displaySkillList[p.normal].activeEffect.srcInstance or { }
	return { vaal = p.vaal, normal = p.normal, on = (src.skillMinion == p.asc) and (g.mainActiveSkill or 1) ~= p.vaal }
end

function es_set_ascend(on)
	local g = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local p = ascendPair(g)
	if p then
		g.mainActiveSkill = p.normal
		local src = g.displaySkillList[p.normal].activeEffect.srcInstance
		local want = on and p.asc or p.base
		if src.skillMinion ~= want then src.skillMinionSkill = nil end
		src.skillMinion = want
		build.modFlag = true
		build.buildFlag = true
		frame()
	end
	return es_summary()
end

function es_set_minion(j)
	local ms, src = mainSrc()
	if ms and src and ms.minionList and ms.minionList[j] then
		if src.skillMinion ~= ms.minionList[j] then src.skillMinionSkill = nil end  -- 소환수가 바뀌면 스킬 목록도 바뀜
		src.skillMinion = ms.minionList[j]
		build.modFlag = true
		build.buildFlag = true
		frame()
	end
	return es_summary()
end

function es_set_minion_skill(j)
	local _, src = mainSrc()
	if src then
		src.skillMinionSkill = j
		build.modFlag = true
		build.buildFlag = true
		frame()
	end
	return es_summary()
end

function es_set_main_group(i)
	build.mainSocketGroup = i
	build.modFlag = true
	build.buildFlag = true
	frame()
	pcall(fixMainActive)  -- 바알 면죄처럼 고른 쪽이 DPS 0 이면 같은 젬의 다른 스킬로
end

function es_set_group(i, enabled, includeInFullDPS)
	local group = build.skillsTab.socketGroupList[i]
	if not group then return false end
	if enabled ~= nil then group.enabled = enabled end
	if includeInFullDPS ~= nil then group.includeInFullDPS = includeInFullDPS end
	build.skillsTab:ProcessSocketGroup(group)
	build.modFlag = true
	build.buildFlag = true
	frame()
	return true
end

-------------------------------------------------------------------------------
-- 패시브 트리 (PoB Tree 탭과 같은 동작: PassiveTreeView / TreeTab 의 클릭 처리)
-------------------------------------------------------------------------------
local function treeChanged()
	build.spec:AddUndoState()
	build.treeTab.modFlag = true
	build.modFlag = true
	build.buildFlag = true
	frame()
end

local function ascendVisible(spec, n)
	if not n.ascendancyName then return true end
	if spec.curAscendClassBaseName and n.ascendancyName == spec.curAscendClassBaseName then return true end
	if spec.curAscendClass and n.ascendancyName == spec.curAscendClass.id then return true end
	if spec.curSecondaryAscendClass and n.ascendancyName == spec.curSecondaryAscendClass.id then return true end
	return false
end

-- 화면에 그릴 노드 배치 (트리 버전 / 클러스터 주얼이 바뀔 때만 다시 받는다)
function es_tree_layout()
	local spec = build.spec
	local tree = spec.tree
	local out = { version = spec.treeVersion, nodes = { }, orbitRadii = tree.orbitRadii }
	for id, n in pairs(spec.nodes) do
		if n.x and n.y and n.group and ascendVisible(spec, n) then
			local linked = { }
			for _, o in ipairs(n.linked or { }) do linked[#linked + 1] = o.id end
			local e = {
				id = id, x = n.x, y = n.y, t = n.type, name = n.dn or n.name or "",
				sd = n.sd or { }, asc = n.ascendancyName, o = n.o, a = n.angle,
				gx = n.group.x, gy = n.group.y, l = linked,
				ascStart = n.isAscendancyStart or nil, cls = n.classStartIndex,
				bloodline = n.isBloodline or nil, cluster = (id >= 65536) or nil,
			}
			if n.type == "Mastery" and n.masteryEffects then
				e.effects = { }
				for _, ef in ipairs(n.masteryEffects) do
					e.effects[#e.effects + 1] = { id = ef.effect, stats = ef.stats }
				end
			end
			out.nodes[#out.nodes + 1] = e
		end
	end
	return out
end

local function layoutKey(spec)
	local n = 0
	for _ in pairs(spec.nodes) do n = n + 1 end
	return tostring(spec.treeVersion) .. ":" .. n .. ":" .. tostring(spec.curAscendClassId) .. ":" .. tostring(spec.curSecondaryAscendClassId or 0)
end

function es_tree_state()
	local spec = build.spec
	local used, ascUsed, secUsed, sockets = spec:CountAllocNodes()
	local extra = build.calcsTab.mainOutput and build.calcsTab.mainOutput.ExtraPoints or 0
	local st = {
		key = layoutKey(spec), alloc = { }, mastery = { }, jewels = { }, granted = { },
		used = used, usedMax = 99 + 23 + extra, ascUsed = ascUsed, ascMax = 8,
		className = spec.curClassName, ascendName = spec.curAscendClassName,
		startId = spec.curClass and spec.curClass.startNodeId,
		snapshot = { classId = spec.curClassId, ascendClassId = spec.curAscendClassId,
			secondaryAscendClassId = spec.curSecondaryAscendClassId or 0, hashList = { }, masteryEffects = { } },
	}
	for id in pairs(spec.allocNodes) do
		st.alloc[#st.alloc + 1] = id
		st.snapshot.hashList[#st.snapshot.hashList + 1] = id
	end
	for nid, eid in pairs(spec.masterySelections) do
		st.mastery[tostring(nid)] = eid
		st.snapshot.masteryEffects[tostring(nid)] = eid
	end
	for nid, slot in pairs(build.itemsTab.sockets or { }) do
		local item = build.itemsTab.items[slot.selItemId]
		if item and spec.allocNodes[nid] then st.jewels[tostring(nid)] = item.name end
	end
	local env = build.calcsTab.mainEnv
	for nid in pairs(env and env.grantedPassives or { }) do st.granted[#st.granted + 1] = nid end
	return st
end

local function idList(t)
	local r = { }
	for _, n in ipairs(t or { }) do r[#r + 1] = n.id end
	return r
end

-- 노드에 마우스를 올렸을 때 (PoB 툴팁의 "Allocating this node will give you" 와 같은 계산)
function es_tree_preview(id)
	local spec = build.spec
	local node = spec.nodes[id]
	if not node then return { error = "no node" } end
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator(build)
	local res = { id = id, alloc = node.alloc and true or false, base = pickStats(calcBase) }
	local env = build.calcsTab.mainEnv
	if node.alloc then
		res.depends = idList(node.depends)
		res.node = pickStats(calcFunc({ removeNodes = { [node] = true } }))
		if #node.depends > 1 then
			local p = { }
			for _, d in ipairs(node.depends) do p[d] = true end
			res.path = pickStats(calcFunc({ removeNodes = p }))
		end
	elseif env and env.grantedPassives and env.grantedPassives[id] then
		res.granted = true
		res.node = pickStats(calcFunc({ removeNodes = { [id] = true } }))
	elseif node.path then
		res.pathIds = idList(node.path)
		if node.type ~= "Mastery" then
			res.node = pickStats(calcFunc({ addNodes = { [node] = true } }))
		end
		if #node.path > 1 then
			local p = { }
			for _, d in ipairs(node.path) do p[d] = true end
			if node.type == "Mastery" then p[node] = nil end
			res.path = pickStats(calcFunc({ addNodes = p }))
		end
	else
		res.unreachable = true
	end
	return res
end

-- 마스터리: 고를 수 있는 효과마다 찍었을 때의 변화
function es_tree_mastery_preview(id)
	local spec = build.spec
	local node = spec.nodes[id]
	if not (node and node.type == "Mastery" and node.masteryEffects) then return { effects = { } } end
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator(build)
	local res = { id = id, base = pickStats(calcBase), effects = { } }
	local cachedSd, cachedAll = node.sd, node.allMasteryOptions
	local cur = spec.masterySelections[id]
	for _, ef in ipairs(node.masteryEffects) do
		local owner = isValueInTable(spec.masterySelections, ef.effect)
		local e = { id = ef.effect, stats = ef.stats, taken = (owner and owner ~= id) or nil, current = (cur == ef.effect) or nil }
		if not e.taken and not e.current then
			local effect = spec.tree.masteryEffects[ef.effect]
			node.sd = effect.sd
			node.allMasteryOptions = false
			spec.tree:ProcessStats(node)
			local add = { [node] = true }
			if not node.alloc then
				for _, p in ipairs(node.path or { }) do add[p] = true end
			end
			e.stats_out = pickStats(calcFunc({ addNodes = add }))
		end
		res.effects[#res.effects + 1] = e
	end
	node.sd, node.allMasteryOptions = cachedSd, cachedAll
	spec.tree:ProcessStats(node)
	return res
end

-- 클릭: 찍혀 있으면 해제(의존 노드 포함), 아니면 경로 포함해서 찍기. 마스터리는 effectId 필요.
function es_tree_click(id, effectId)
	local spec = build.spec
	local node = spec.nodes[id]
	if not node then return { error = "노드를 찾을 수 없습니다" } end
	if node.type == "Mastery" and effectId then
		local effect = spec.tree.masteryEffects[effectId]
		if not effect then return { error = "마스터리 효과를 찾을 수 없습니다" } end
		if not node.alloc and not node.path then return { error = "연결된 경로가 없습니다" } end
		node.sd = effect.sd
		node.allMasteryOptions = false
		node.reminderText = { "Tip: Right click to select a different effect" }
		spec.tree:ProcessStats(node)
		spec.masterySelections[id] = effectId
		if not node.alloc then spec:AllocNode(node) else spec:BuildAllDependsAndPaths() end
	elseif node.alloc then
		spec:DeallocNode(node)
	else
		if not node.path then return { error = "트리에 연결할 경로가 없습니다" } end
		if node.type == "Mastery" then return { error = "마스터리 효과를 골라 주세요" } end
		spec:AllocNode(node)
	end
	treeChanged()
	return { ok = true }
end

function es_tree_restore(snapJson)
	local snap = (require "dkjson").decode(snapJson) or { }
	local spec = build.spec
	local hl, me = { }, { }
	for _, id in ipairs(snap.hashList or { }) do hl[#hl + 1] = tonumber(id) end
	for k, v in pairs(snap.masteryEffects or { }) do me[tonumber(k)] = tonumber(v) end
	spec:ImportFromNodeList(nil, tonumber(snap.classId) or spec.curClassId, tonumber(snap.ascendClassId) or 0,
		tonumber(snap.secondaryAscendClassId) or 0, hl, spec.hashOverrides, me, spec.treeVersion)
	treeChanged()
	return { ok = true }
end

function es_tree_reset()
	local spec = build.spec
	spec:ResetNodes()
	spec:BuildAllDependsAndPaths()
	treeChanged()
	return { ok = true }
end

function es_tree_import_url(url)
	local spec = build.spec
	local err = spec:DecodeURL(url)
	if err then return { error = err } end
	spec:BuildAllDependsAndPaths()
	treeChanged()
	return { ok = true }
end

-------------------------------------------------------------------------------
-- 장착 장비 / 주얼 (PoB Items 탭의 슬롯 드롭다운과 같은 동작)
-------------------------------------------------------------------------------
local EQUIP_SLOTS = { "Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet",
	"Ring 1", "Ring 2", "Ring 3", "Belt" }

local function itemLines(item)
	local out = { }
	for _, key in ipairs({ "enchantModLines", "scourgeModLines", "implicitModLines", "explicitModLines", "crucibleModLines" }) do
		for _, ml in ipairs(item[key] or { }) do
			if item:CheckModLineVariant(ml) and ml.line and ml.line ~= "" then
				out[#out + 1] = { line = ml.line, kind = key:gsub("ModLines", ""),
					crafted = ml.crafted or nil, fractured = ml.fractured or nil }
			end
		end
	end
	return out
end

local function itemInfo(item)
	if not item then return nil end
	return { id = item.id, name = item.name, title = item.title, base = item.baseName, rarity = item.rarity,
		corrupted = item.corrupted or nil, quality = item.quality, lines = itemLines(item) }
end

-- 클러스터 주얼을 빼면 그 안에 찍은 노드가 사라지므로, 다시 끼울 때 복원할 수 있게 기억해 둔다
local clusterMemory = { }

function allocIds()
	local t = { }
	for id in pairs(build.spec.allocNodes) do t[#t + 1] = id end
	return t
end

function reallocIds(ids)
	local spec = build.spec
	for _, id in ipairs(ids) do
		local n = spec.nodes[id]
		if n and not n.alloc then
			n.alloc = true
			spec.allocNodes[id] = n
		end
	end
	spec:BuildAllDependsAndPaths()
end

local function sortedJewelSockets()
	local itemsTab = build.itemsTab
	itemsTab:UpdateSockets()
	local ids = { }
	for nodeId in pairs(itemsTab.sockets) do
		if build.spec.allocNodes[nodeId] then ids[#ids + 1] = nodeId end
	end
	table.sort(ids)
	return ids
end

function es_equipment()
	local itemsTab = build.itemsTab
	itemsTab:PopulateSlots()
	local res = { slots = { } }
	local function add(slotName, slot, kind, label)
		local opts = { }
		for _, id in ipairs(slot.items or { }) do
			local it = itemsTab.items[id]
			if it then opts[#opts + 1] = { id = id, name = it.name, rarity = it.rarity } end
		end
		res.slots[#res.slots + 1] = { slot = slotName, kind = kind, label = label, nodeId = slot.nodeId,
			item = itemInfo(itemsTab.items[slot.selItemId]), options = opts }
	end
	local useSecond = itemsTab.activeItemSet.useSecondWeaponSet
	for _, name in ipairs(EQUIP_SLOTS) do
		local sname = name
		if useSecond and name:match("^Weapon") then sname = name .. " Swap" end
		local slot = itemsTab.slots[sname]
		if slot and not slot.inactive and (name ~= "Ring 3" or slot.selItemId ~= 0 or (slot.shown and slot.shown())) then
			if name ~= "Ring 3" or slot.selItemId ~= 0 then add(sname, slot, "gear", name) end
			-- 장비에 박힌 심연 주얼
			for i = 1, 6 do
				local ab = itemsTab.slots[sname .. " Abyssal Socket " .. i]
				if ab and not ab.inactive then add(ab.slotName, ab, "abyss", name .. " Abyssal " .. i) end
			end
		end
	end
	for i, nodeId in ipairs(sortedJewelSockets()) do
		add("Jewel " .. nodeId, itemsTab.sockets[nodeId], "jewel", "Socket " .. i)
	end
	return res
end

-- 각 슬롯을 비웠을 때의 계산 결과 (이 장비가 주는 몫)
-- skip/limit: 젬 영향과 같은 방식으로 나눠 계산 (남으면 res.next)
function es_equipment_impact(skip, limit)
	skip, limit = skip or 0, limit or 1e9
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local res = { base = pickStats(calcBase), slots = { } }
	local itemsTab = build.itemsTab
	local eq = es_equipment()
	local light, heavy = { }, { }
	for _, s in ipairs(eq.slots) do
		if s.item then
			local b = s.item.base or ""
			if s.kind == "jewel" and (b:find("Cluster Jewel") or b:find("Timeless Jewel")) then
				heavy[#heavy + 1] = s  -- 트리 자체를 바꾸는 주얼: 실제로 빼서 다시 계산
			else
				light[#light + 1] = s
			end
		end
	end
	-- 이번 범위만 (가벼운 것 → 무거운 것 순서)
	local all = { }
	for _, s in ipairs(light) do all[#all + 1] = { s = s } end
	for _, s in ipairs(heavy) do all[#all + 1] = { s = s, heavy = true } end
	local last = math.min(#all, skip + limit)
	if last < #all then res.next = last end
	light, heavy = { }, { }
	for k = skip + 1, last do
		if all[k].heavy then heavy[#heavy + 1] = all[k].s else light[#light + 1] = all[k].s end
	end
	for _, s in ipairs(light) do
		res.slots[s.slot] = pickStats(calcFunc({ repSlotName = s.slot }))
	end
	for _, s in ipairs(heavy) do
		local slot = itemsTab.slots[s.slot]
		local id = slot.selItemId
		local before = allocIds()
		slot:SetSelItemId(0)
		build.buildFlag = true
		frame()
		res.slots[s.slot] = pickStats(build.calcsTab.mainOutput)
		slot:SetSelItemId(id)
		reallocIds(before)
		build.buildFlag = true
		frame()
	end
	return res
end

function es_set_slot(slotName, itemId)
	local itemsTab = build.itemsTab
	local slot = itemsTab.slots[slotName]
	if not slot then return { error = "슬롯을 찾을 수 없습니다: " .. tostring(slotName) } end
	itemId = tonumber(itemId) or 0
	if itemId ~= 0 and not (itemsTab.items[itemId] and itemsTab:IsItemValidForSlot(itemsTab.items[itemId], slotName)) then
		return { error = "이 슬롯에 넣을 수 없는 아이템입니다" }
	end
	-- 같은 아이템이 다른 슬롯에 끼어 있으면 그 슬롯은 비운다 (실제 게임처럼 한 곳에만)
	if itemId ~= 0 then
		for name, other in pairs(itemsTab.slots) do
			if name ~= slotName and other.selItemId == itemId then other:SetSelItemId(0) end
		end
	end
	local oldId = slot.selItemId
	local before = slot.nodeId and oldId ~= 0 and allocIds()
	slot:SetSelItemId(itemId)
	if before then
		-- 빼면서 사라진 노드(클러스터 안에 찍은 노드)를 기억
		local lost = { }
		for _, id in ipairs(before) do
			if not build.spec.allocNodes[id] then lost[#lost + 1] = id end
		end
		if #lost > 0 then clusterMemory[slotName .. ":" .. oldId] = lost end
	end
	local mem = slot.nodeId and clusterMemory[slotName .. ":" .. itemId]
	if mem then reallocIds(mem) end
	itemsTab:PopulateSlots()
	itemsTab:AddUndoState()
	build.modFlag = true
	build.buildFlag = true
	frame()
	return { ok = true }
end

-------------------------------------------------------------------------------
-- 플라스크 (Items 탭 맨 위와 같은 활성 체크 + 켜고 끌 때 변화)
-------------------------------------------------------------------------------
function es_flasks()
	local itemsTab = build.itemsTab
	itemsTab:PopulateSlots()
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local res = { base = pickStats(calcBase), flasks = { } }
	for n = 1, 5 do
		local sname = "Flask " .. n
		local slot = itemsTab.slots[sname]
		if slot then
			local item = itemsTab.items[slot.selItemId]
			local opts = { }
			for _, id in ipairs(slot.items or { }) do
				local it = itemsTab.items[id]
				if it then opts[#opts + 1] = { id = id, name = it.name, rarity = it.rarity } end
			end
			local e = { slot = sname, active = slot.active == true, item = itemInfo(item), options = opts }
			if item then
				-- 켜져 있으면 껐을 때, 꺼져 있으면 켰을 때 (PoB 툴팁과 같은 toggleFlask)
				e.toggled = pickStats(calcFunc({ toggleFlask = item }))
			end
			res.flasks[#res.flasks + 1] = e
		end
	end
	return res
end

-------------------------------------------------------------------------------
-- 아이템 만들기 (PoB 의 Craft item / 유니크·레어 DB / 아이템 텍스트 붙여넣기)
-- 작업 중인 아이템(esDraft)을 Lua 쪽에 두고 조금씩 바꾼다.
-------------------------------------------------------------------------------
local esDraft = nil
local CATALYST_NAMES = { "Abrasive", "Accelerating", "Dextral", "Fertile", "Imbued", "Intrinsic", "Noxious", "Prismatic",
	"Sinistral", "Tempering", "Turbulent", "Unstable" }
local esDraftSlot = nil

local function ensureItemDBs()
	local n = 0
	while (main.uniqueDB.loading or main.rareDB.loading) and n < 5000 do
		frame()
		n = n + 1
	end
end

local function makeBaseItem(baseEntry, rarity, title)
	local item = new("Item")
	item.name = baseEntry.name
	item.base = baseEntry.base
	item.baseName = baseEntry.name
	item.buffModLines = { }
	item.enchantModLines = { }
	item.classRequirementModLines = { }
	item.scourgeModLines = { }
	item.implicitModLines = { }
	item.explicitModLines = { }
	item.crucibleModLines = { }
	local t = baseEntry.base.type
	if t == "Amulet" or t == "Belt" or t == "Jewel" or t == "Quiver" or t == "Ring" or t == "Graft" then
		item.quality = nil
	else
		item.quality = 0
	end
	if (baseEntry.base.flask or t == "Tincture" or (t == "Jewel" and baseEntry.base.subType == "Charm")) and rarity == "RARE" then
		rarity = "MAGIC"
	end
	if rarity == "MAGIC" or rarity == "RARE" then item.crafted = true end
	item.rarity = rarity
	if rarity == "RARE" then item.title = (title and title:match("%S")) and title or "New Item" end
	if baseEntry.base.implicit then
		local i = 1
		for line in baseEntry.base.implicit:gmatch("[^\n]+") do
			local modList, extra = modLib.parseMod(line)
			table.insert(item.implicitModLines, { line = line, extra = extra, modList = modList or { },
				modTags = baseEntry.base.implicitModTypes and baseEntry.base.implicitModTypes[i] or { } })
			i = i + 1
		end
	end
	item:NormaliseQuality()
	item:BuildAndParseRaw()
	if item.crafted then item:Craft() end
	return item
end

local function findBase(name)
	for _, list in pairs(data.itemBaseLists) do
		for _, b in ipairs(list) do
			if b.name == name then return b end
		end
	end
end

-- 슬롯에 넣을 수 있는 유니크 / 레어 템플릿 / 베이스 목록
function es_item_catalog(slotName)
	ensureItemDBs()
	local itemsTab = build.itemsTab
	local function valid(it)
		local ok, r = pcall(function() return itemsTab:IsItemValidForSlot(it, slotName) end)
		return ok and r
	end
	local res = { uniques = { }, rares = { }, baseTypes = { } }
	for name, it in pairs(main.uniqueDB.list) do
		if valid(it) then
			res.uniques[#res.uniques + 1] = { name = name, base = it.baseName, level = it.requirements and it.requirements.level or 0 }
		end
	end
	for name, it in pairs(main.rareDB.list) do
		if valid(it) then res.rares[#res.rares + 1] = { name = name, base = it.baseName } end
	end
	for _, typeName in ipairs(data.itemBaseTypeList) do
		local list = data.itemBaseLists[typeName]
		local ok, sample = pcall(makeBaseItem, list[1], "NORMAL")
		if ok and sample and valid(sample) then
			local bases = { }
			for _, b in ipairs(list) do
				bases[#bases + 1] = { name = b.name, level = b.base.req and b.base.req.level or 0, implicit = b.base.implicit }
			end
			res.baseTypes[#res.baseTypes + 1] = { type = typeName, bases = bases }
		end
	end
	table.sort(res.uniques, function(a, b) return a.name < b.name end)
	table.sort(res.rares, function(a, b) return a.name < b.name end)
	return res
end

local function lineInfo(item, ml, kind, idx)
	local hasRange = ml.line:match("%(%-?[%d%.]+%-%-?[%d%.]+%)") ~= nil
	local shown = hasRange and itemLib.applyRange(ml.line, ml.range or main.defaultItemAffixQuality or 0.5, ml.valueScalar or 1) or ml.line
	return { kind = kind, idx = idx, line = shown, template = ml.line, hasRange = hasRange or nil,
		range = ml.range, crafted = ml.crafted or nil, prefix = ml.prefix or nil, suffix = ml.suffix or nil,
		active = item:CheckModLineVariant(ml) or nil }
end

local affixCache = { }

-- 접두/접미로 고를 수 있는 옵션 묶음 (PoB UpdateAffixControl 과 같은 묶음: statOrder 가 같은 티어들을 한 줄로)
local function affixGroups(item, affixType)
	local inf = ""
	for _, ii in ipairs(itemLib.influenceInfo.default) do if item[ii.key] then inf = inf .. ii.key .. "," end end
	local key = tostring(item.baseName) .. "|" .. tostring(item.rarity) .. "|" .. affixType .. "|" .. inf
	if affixCache[key] then return affixCache[key] end
	local list = { }
	for modId, mod in pairs(item.affixes or { }) do
		if mod.type == affixType and not item:CheckIfModIsDelve(mod) and item:CanHaveMod(mod, { }) then
			list[#list + 1] = modId
		end
	end
	table.sort(list, function(a, b)
		local ma, mb = item.affixes[a], item.affixes[b]
		for i = 1, math.max(#ma, #mb) do
			if not ma[i] then return true elseif not mb[i] then return false
			elseif ma.statOrder[i] ~= mb.statOrder[i] then return ma.statOrder[i] < mb.statOrder[i] end
		end
		if ma.level ~= mb.level then return ma.level < mb.level end
		return a < b
	end)
	local groups, last, lastOrder = { }, nil, nil
	for _, modId in ipairs(list) do
		local mod = item.affixes[modId]
		local orderKey = table.concat(mod.statOrder, ",")
		if not last or lastOrder ~= orderKey then
			last = { label = table.concat(mod, " / "), group = mod.group, tiers = { } }
			groups[#groups + 1] = last
			lastOrder = orderKey
		end
		last.tiers[#last.tiers + 1] = { modId = modId, text = table.concat(mod, " / "), level = mod.level, affix = mod.affix }
		if #last.tiers == 2 then
			last.label = last.label:gsub("%(%-?[%d%.]+%-%-?[%d%.]+%)", "#"):gsub("%-?%d+%.?%d*", "#")
		end
	end
	affixCache[key] = groups
	return groups
end

local function draftInfo(withAffixes)
	local item = esDraft
	if not item then return { error = "no draft" } end
	local info = { name = item.name, title = item.title, base = item.baseName, rarity = item.rarity,
		crafted = item.crafted or nil, quality = item.quality, raw = item:BuildRaw(), lines = { },
		variants = item.variantList, variant = item.variant, affixLimit = item.affixLimit,
		catalyst = item.catalyst and CATALYST_NAMES[item.catalyst] or nil, catalystQuality = item.catalystQuality, influences = { } }
	for _, ii in ipairs(itemLib.influenceInfo.default) do
		if item[ii.key] then info.influences[#info.influences + 1] = ii.display end
	end
	for _, key in ipairs({ "enchant", "implicit", "explicit" }) do
		for i, ml in ipairs(item[key .. "ModLines"] or { }) do
			info.lines[#info.lines + 1] = lineInfo(item, ml, key, i)
		end
	end
	if withAffixes and not item.crafted and item.affixes and item.rarity ~= "UNIQUE" and item.rarity ~= "RELIC" then
		-- 게임에서 가져온 일반·마법·희귀 아이템: 줄마다 옵션 목록에서 골라 바꿀 수 있게
		info.prefixGroups = affixGroups(item, "Prefix")
		info.suffixGroups = affixGroups(item, "Suffix")
	end
	if item.crafted and item.affixes then
		local pl = item.prefixes.limit or (item.affixLimit / 2)
		local sl = item.suffixes.limit or (item.affixLimit / 2)
		info.prefixLimit, info.suffixLimit = pl, sl
		info.prefixes, info.suffixes = { }, { }
		for i = 1, pl do local a = item.prefixes[i] or { } info.prefixes[i] = { modId = a.modId or "None", range = a.range } end
		for i = 1, sl do local a = item.suffixes[i] or { } info.suffixes[i] = { modId = a.modId or "None", range = a.range } end
		if withAffixes then
			info.prefixGroups = affixGroups(item, "Prefix")
			info.suffixGroups = affixGroups(item, "Suffix")
		end
	end
	-- 대상 슬롯에 꼈을 때 (지금 장비 대비)
	if esDraftSlot and build.itemsTab.slots[esDraftSlot] then
		local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
		info.base_stats = pickStats(calcBase)
		local ok, out = pcall(calcFunc, { repSlotName = esDraftSlot, repItem = item })
		if ok then info.stats = pickStats(out) end
		info.valid = build.itemsTab:IsItemValidForSlot(item, esDraftSlot) or nil
	end
	return info
end

function es_draft_new(specJson)
	local spec = (require "dkjson").decode(specJson) or { }
	ensureItemDBs()
	esDraftSlot = spec.slot
	local item
	if spec.from == "unique" then
		local src = main.uniqueDB.list[spec.name]
		if not src then return { error = "유니크를 찾을 수 없습니다" } end
		item = new("Item", src:BuildRaw())
	elseif spec.from == "rare" then
		local src = main.rareDB.list[spec.name]
		if not src then return { error = "템플릿을 찾을 수 없습니다" } end
		item = new("Item", src:BuildRaw())
	elseif spec.from == "base" then
		local b = findBase(spec.base)
		if not b then return { error = "베이스를 찾을 수 없습니다" } end
		item = makeBaseItem(b, spec.rarity or "RARE", spec.title)
	elseif spec.from == "equipped" then
		local slot = build.itemsTab.slots[spec.slot]
		local src = slot and build.itemsTab.items[slot.selItemId]
		if not src then return { error = "장착된 아이템이 없습니다" } end
		item = new("Item", src:BuildRaw())
	else
		item = new("Item", spec.raw or "")
	end
	if not item or not item.base then return { error = "아이템을 해석하지 못했습니다" } end
	item:BuildModList()
	esDraft = item
	return draftInfo(true)
end

function es_draft_edit(specJson)
	local spec = (require "dkjson").decode(specJson) or { }
	local item = esDraft
	if not item then return { error = "no draft" } end
	if spec.variant then
		item.variant = tonumber(spec.variant)
		item:BuildAndParseRaw()
	end
	if spec.quality ~= nil and item.quality ~= nil then
		item.quality = tonumber(spec.quality) or item.quality
		item:BuildAndParseRaw()
	end
	if spec.title and item.rarity == "RARE" then
		item.title = spec.title
		item:BuildAndParseRaw()
	end
	if spec.range then
		-- {kind, idx, value}: 유동 수치 한 줄
		local ml = (item[spec.range.kind .. "ModLines"] or { })[tonumber(spec.range.idx)]
		if ml then
			ml.range = math.max(0, math.min(1, tonumber(spec.range.value) or 0.5))
			item:BuildAndParseRaw()
		end
	end
	if spec.allRange then
		for _, key in ipairs({ "implicit", "explicit" }) do
			for _, ml in ipairs(item[key .. "ModLines"] or { }) do
				if ml.line:match("%(%-?[%d%.]+%-%-?[%d%.]+%)") then ml.range = tonumber(spec.allRange) end
			end
		end
		item:BuildAndParseRaw()
	end
	if spec.affix and item.crafted then
		local a = spec.affix  -- {table="prefixes"/"suffixes", index, modId, range}
		item[a.table][tonumber(a.index)] = { modId = a.modId or "None", range = tonumber(a.range) or 0.5 }
		item:Craft()
	end
	if spec.line then
		-- 옵션 한 줄 고치기 / 지우기 (text 가 "" 이면 삭제) — 범위 없는 일반 레어·게임에서 가져온 아이템용
		local lines = item[spec.line.kind .. "ModLines"]
		local i = tonumber(spec.line.idx)
		if lines and lines[i] then
			if spec.line.text == nil or spec.line.text == "" then
				table.remove(lines, i)
			else
				lines[i].line = spec.line.text
				lines[i].range = nil
			end
			item:BuildAndParseRaw()
		end
	end
	if spec.setMod then
		-- 옵션 목록에서 고른 옵션으로 한 줄 바꾸기(idx) 또는 추가(idx 없음). 수치는 PoB 와 같은 applyRange
		local s = spec.setMod
		local mod = item.affixes and item.affixes[s.modId]
		if mod then
			local key = (s.kind or "explicit") .. "ModLines"
			item[key] = item[key] or { }
			local lines = item[key]
			local newLines = { }
			for _, l in ipairs(mod) do
				local ml = { line = itemLib.applyRange(l, tonumber(s.range) or 0.5), modTags = mod.modTags or { } }
				if mod.type == "Prefix" then ml.prefix = true elseif mod.type == "Suffix" then ml.suffix = true end
				newLines[#newLines + 1] = ml
			end
			local idx = tonumber(s.idx)
			if idx and lines[idx] then
				table.remove(lines, idx)
				for k = #newLines, 1, -1 do table.insert(lines, idx, newLines[k]) end
			else
				for _, nl in ipairs(newLines) do table.insert(lines, nl) end
			end
			item:BuildAndParseRaw()
		end
	end
	if spec.addLine and spec.addLine.text and spec.addLine.text ~= "" then
		local key = (spec.addLine.kind or "explicit") .. "ModLines"
		item[key] = item[key] or { }
		local ml = { line = spec.addLine.text, modTags = { } }
		if spec.addLine.crafted then ml.crafted = true end
		table.insert(item[key], ml)
		item:BuildAndParseRaw()
	end
	if spec.raw then
		local it = new("Item", spec.raw)
		if it and it.base then item = it esDraft = it end
	end
	item:BuildModList()
	return draftInfo(spec.affix == nil and spec.raw ~= nil)
end

function es_draft_info()
	return draftInfo(true)
end

-------------------------------------------------------------------------------
-- (베타) 슬롯별 DPS 최적 옵션 찾기
--   1) 접두·접미 옵션을 하나씩 붙여 DPS 순으로 줄 세움
--   2) 상위 3+3 으로 시작 → 한 칸씩 다른 후보로 바꿔 보며 더 좋아지면 교체 (시너지·캡 반영)
--   지금 템보다 DPS 가 낮게 나와도 가장 덜 떨어지는 조합을 돌려준다.
-------------------------------------------------------------------------------
local INFLUENCES = { "shaper", "elder", "adjudicator", "basilisk", "crusader", "eyrie" }
local CATALYSTS = { "Abrasive", "Accelerating", "Dextral", "Fertile", "Imbued", "Intrinsic", "Noxious", "Prismatic",
	"Sinistral", "Tempering", "Turbulent", "Unstable" }

function es_optimize(specJson)
	local spec = (require "dkjson").decode(specJson) or { }
	ensureItemDBs()
	local slotName = spec.slot
	local itemsTab = build.itemsTab
	local slot = itemsTab.slots[slotName]
	if not slot then return { error = "슬롯을 찾을 수 없습니다" } end
	local cur = itemsTab.items[slot.selItemId]
	local baseName = (spec.base and spec.base ~= "") and spec.base or (cur and cur.baseName)
	local b = baseName and findBase(baseName)
	if not b then return { error = "베이스를 골라 주세요 (지금 이 슬롯이 비어 있음)" } end
	local item = makeBaseItem(b, "RARE", "DPS Optimized")
	if not item.affixes or not itemsTab:IsItemValidForSlot(item, slotName) then
		return { error = "이 슬롯에 넣을 수 없는 베이스입니다" }
	end
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local key = (calcBase.FullDPS and calcBase.FullDPS > 0) and "FullDPS" or "CombinedDPS"
	local rng = tonumber(spec.range) or 1
	local tierLimit = math.max(1, tonumber(spec.tier) or 1)
	local pl = item.prefixes.limit or (item.affixLimit / 2)
	local sl = item.suffixes.limit or (item.affixLimit / 2)
	local nCalc = 0
	local t = b.base.type
	local jewellery = (t == "Ring" or t == "Amulet" or t == "Belt")
	local canInfluence = spec.influence ~= false and item.base.influenceTags ~= nil
	local useCatalyst = spec.catalyst ~= false and jewellery

	local function setInfluences(list)
		for _, k in ipairs(INFLUENCES) do item[k] = nil end
		for _, k in ipairs(list or { }) do item[k] = true end
	end
	local function setAffixes(pre, suf)
		for i = 1, pl do item.prefixes[i] = { modId = pre[i] or "None", range = rng } end
		for i = 1, sl do item.suffixes[i] = { modId = suf[i] or "None", range = rng } end
		item:Craft()
	end
	local function score(pre, suf)
		setAffixes(pre, suf)
		nCalc = nCalc + 1
		local out = calcFunc({ repSlotName = slotName, repItem = item })
		return out[key] or 0, out
	end
	local function ids(list) local r = { } for i, c in ipairs(list) do r[i] = c.modId end return r end
	local function cands(groups, kind)
		local list = { }
		for _, g in ipairs(groups) do
			if spec.noSocketed and g.label:match("^Socketed Gems") then goto continue end
			do
			local n = #g.tiers
			local idx = math.max(1, n - tierLimit + 1)
			local tt = g.tiers[idx]
			list[#list + 1] = { modId = tt.modId, group = g.group, label = g.label, text = tt.text,
				tier = n - idx + 1, level = tt.level, kind = kind }
			end
			::continue::
		end
		return list
	end
	local function pick(list, n, used)
		local out = { }
		for _, c in ipairs(list) do
			if #out >= n then break end
			if not (c.group and used[c.group]) then
				out[#out + 1] = c
				if c.group then used[c.group] = true end
			end
		end
		return out
	end

	-- 한 가지 영향력 조합(+촉매)에서 최적 6옵션
	local function core(infl)
		setInfluences(infl)
		local preC = cands(affixGroups(item, "Prefix"), "prefix")
		local sufC = cands(affixGroups(item, "Suffix"), "suffix")
		local empty = score({ }, { })
		for _, c in ipairs(preC) do c.solo = score({ c.modId }, { }) - empty end
		for _, c in ipairs(sufC) do c.solo = score({ }, { c.modId }) - empty end
		table.sort(preC, function(x, y) return x.solo > y.solo end)
		table.sort(sufC, function(x, y) return x.solo > y.solo end)
		local used = { }
		local pre = pick(preC, pl, used)
		local suf = pick(sufC, sl, used)
		local best, bestOut = score(ids(pre), ids(suf))
		local K = 14
		for _ = 1, 10 do
			local bestSwap
			for _, side in ipairs({ { list = pre, cand = preC, lim = pl }, { list = suf, cand = sufC, lim = sl } }) do
				local usedG = { }
				for _, c in ipairs(pre) do if c.group then usedG[c.group] = (usedG[c.group] or 0) + 1 end end
				for _, c in ipairs(suf) do if c.group then usedG[c.group] = (usedG[c.group] or 0) + 1 end end
				local positions = #side.list < side.lim and (#side.list + 1) or #side.list
				for p = 1, positions do
					local old = side.list[p]
					for ci = 1, math.min(K, #side.cand) do
						local c = side.cand[ci]
						local inUse = false
						for _, x in ipairs(side.list) do if x.modId == c.modId then inUse = true end end
						local gUsed = c.group and ((usedG[c.group] or 0) - ((old and old.group == c.group) and 1 or 0)) > 0
						if not inUse and not gUsed then
							side.list[p] = c
							local s, out = score(ids(pre), ids(suf))
							side.list[p] = old
							if s > best * 1.0000001 + 1e-9 and (not bestSwap or s > bestSwap.s) then
								bestSwap = { side = side, p = p, c = c, s = s, out = out }
							end
						end
					end
				end
			end
			if not bestSwap then break end
			bestSwap.side.list[bestSwap.p] = bestSwap.c
			best, bestOut = bestSwap.s, bestSwap.out
		end
		return { infl = infl, best = best, out = bestOut, pre = pre, suf = suf, preC = preC, sufC = sufC, empty = empty }
	end

	-- 영향력: 없음 / 하나씩 6가지 → 효과 있던 상위 영향력끼리 2개 조합 (한 아이템 최대 2개)
	local tried = { }
	local function try(infl)
		local r = core(infl)
		tried[#tried + 1] = { infl = infl, best = r.best }
		return r
	end
	local bestR = try({ })
	if canInfluence then
		local singles = { }
		for _, k in ipairs(INFLUENCES) do
			local r = try({ k })
			singles[#singles + 1] = r
			if r.best > bestR.best then bestR = r end
		end
		table.sort(singles, function(x, y) return x.best > y.best end)
		local top = { }
		for i = 1, math.min(4, #singles) do
			if singles[i].best > tried[1].best * 1.0005 then top[#top + 1] = singles[i].infl[1] end
		end
		for i = 1, #top do
			for j = i + 1, #top do
				local r = try({ top[i], top[j] })
				if r.best > bestR.best then bestR = r end
			end
		end
	end

	-- 악세서리: 특수 퀄리티(촉매) 20% 중 가장 좋은 것 → 그 촉매 기준으로 옵션 다시 다듬기
	local bestCat
	if useCatalyst then
		setInfluences(bestR.infl)
		local baseScore = bestR.best
		local bestCatScore = baseScore
		for ci = 1, #CATALYSTS do
			item.catalyst = ci
			item.catalystQuality = 20
			local s = score(ids(bestR.pre), ids(bestR.suf))
			if s > bestCatScore * 1.0000001 then bestCat, bestCatScore = ci, s end
		end
		if bestCat then
			item.catalyst = bestCat
			item.catalystQuality = 20
			local r = core(bestR.infl)
			if r.best >= bestCatScore then bestR = r
			else
				bestR.best = bestCatScore
				bestR.best, bestR.out = score(ids(bestR.pre), ids(bestR.suf))
			end
		else
			item.catalyst = nil
			item.catalystQuality = nil
		end
	end
	setInfluences(bestR.infl)
	local pre, suf, best = bestR.pre, bestR.suf, bestR.best

	-- 고른 옵션마다 기여도 (그 옵션만 뺐을 때 DPS 감소)
	local chosen = { }
	for _, side in ipairs({ pre, suf }) do
		for i, c in ipairs(side) do
			local saved = side[i]
			table.remove(side, i)
			local s = score(ids(pre), ids(suf))
			table.insert(side, i, saved)
			chosen[#chosen + 1] = { modId = c.modId, label = c.label, text = c.text, tier = c.tier, kind = c.kind,
				solo = c.solo, contrib = best - s }
		end
	end
	local _, finalOut = score(ids(pre), ids(suf))
	item:BuildModList()
	esDraft = item
	esDraftSlot = slotName
	local function rank(list)
		local r = { }
		for i, c in ipairs(list) do
			if i > 20 then break end
			r[#r + 1] = { label = c.label, text = c.text, tier = c.tier, solo = c.solo }
		end
		return r
	end
	local inflNames = { }
	for _, k in ipairs(bestR.infl) do
		for _, ii in ipairs(itemLib.influenceInfo.default) do if ii.key == k then inflNames[#inflNames + 1] = ii.display end end
	end
	return { key = key, empty = bestR.empty, base = pickStats(calcBase), final = pickStats(finalOut),
		current = cur and cur.name or "", baseName = baseName, chosen = chosen,
		mainSlot = (build.skillsTab.socketGroupList[build.mainSocketGroup] or { }).slot,
		influences = inflNames, catalyst = bestCat and CATALYSTS[bestCat] or nil,
		quality = item.quality, jewellery = jewellery or nil, canInfluence = canInfluence or nil,
		tried = #tried, prefixRank = rank(bestR.preC), suffixRank = rank(bestR.sufC), calcs = nCalc, draft = draftInfo(true) }
end
-- 지금 장착된 아이템을 고친 내용으로 바꿔치기 (같은 아이템 id — 빌드 아이템 목록이 늘지 않음)
function es_draft_replace(slotName)
	local item = esDraft
	if not item then return { error = "no draft" } end
	local itemsTab = build.itemsTab
	local slot = itemsTab.slots[slotName]
	local old = slot and itemsTab.items[slot.selItemId]
	if not old then return es_draft_equip(slotName) end
	local fresh = new("Item", item:BuildRaw())
	fresh.id = old.id
	local before = slot.nodeId and allocIds()
	itemsTab:AddItem(fresh, true)  -- 같은 id 면 교체 (클러스터 주얼이면 PoB 가 트리 다시 구성)
	if before then reallocIds(before) end
	itemsTab:PopulateSlots()
	itemsTab:AddUndoState()
	build.modFlag = true
	build.buildFlag = true
	frame()
	return { ok = true }
end

-- 만든 아이템을 빌드에 추가하고 슬롯에 장착
function es_draft_equip(slotName)
	local item = esDraft
	if not item then return { error = "no draft" } end
	local itemsTab = build.itemsTab
	if not itemsTab:IsItemValidForSlot(item, slotName) then return { error = "이 슬롯에 넣을 수 없는 아이템입니다" } end
	local fresh = new("Item", item:BuildRaw())
	itemsTab:AddItem(fresh, true)
	return es_set_slot(slotName, fresh.id)
end

-------------------------------------------------------------------------------
-- 스킬 젬 레벨 / 퀄리티 (PoB Skills 탭의 Level / Quality 칸과 같은 처리)
-------------------------------------------------------------------------------
function es_set_gem(groupIdx, gemIdx, level, quality, enabled)
	local group = build.skillsTab.socketGroupList[groupIdx]
	local gem = group and group.gemList[gemIdx]
	if not gem then return { error = "젬을 찾을 수 없습니다" } end
	if level then gem.level = math.max(1, math.floor(level)) end
	if quality then gem.quality = math.max(0, math.floor(quality)) end
	if enabled ~= nil then gem.enabled = enabled and true or false end
	build.skillsTab:ProcessSocketGroup(group)
	build.skillsTab:AddUndoState()
	build.modFlag = true
	build.buildFlag = true
	frame()
	return { ok = true }
end

-- 젬마다 레벨 +1 / -1, 퀄리티 +5 했을 때의 결과 (실제로 바꿔 계산하고 되돌림)
-- skip/limit: 앞에서 skip 개를 건너뛰고 limit 개만 (나눠 계산 → 그 사이 Ctrl+C 비교 등이 끼어들 수 있게).
-- 남은 젬이 있으면 res.next = 다음 skip.
function es_gem_impact(skip, limit)
	skip, limit = skip or 0, limit or 1e9
	local res = { base = pickStats(build.calcsTab.mainOutput), gems = { } }
	local k, done = 0, 0
	local function run(group, gem, field, value)
		local old = gem[field]
		gem[field] = value
		build.skillsTab:ProcessSocketGroup(group)
		build.buildFlag = true
		frame()
		local out = pickStats(build.calcsTab.mainOutput)
		gem[field] = old
		build.skillsTab:ProcessSocketGroup(group)
		return out
	end
	for gi, group in ipairs(build.skillsTab.socketGroupList) do
		if group.enabled ~= false then
			for i, gem in ipairs(group.gemList or { }) do
				if gem.enabled ~= false and gem.gemData and not gem.fromItem then
					k = k + 1
					if k > skip then
						if done >= limit then
							res.next = k - 1
							break
						end
						local e = { group = gi, gem = i }
						e.up = run(group, gem, "level", (gem.level or 1) + 1)
						if (gem.level or 1) > 1 then e.down = run(group, gem, "level", gem.level - 1) end
						e.qual = run(group, gem, "quality", (gem.quality or 0) + 5)
						res.gems[#res.gems + 1] = e
						done = done + 1
					end
				end
			end
		end
		if res.next then break end
	end
	if done > 0 then
		build.buildFlag = true
		frame()
	end
	return res
end

-- Compare an item (PoB/game English item text) against every slot it fits.
function es_compare_item(itemText)
	local item = new("Item", itemText)
	if not item.base then
		return { error = "item could not be parsed" }
	end
	item:BuildModList()
	local itemsTab = build.itemsTab
	itemsTab:UpdateSockets()
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local res = { name = item.name, base = item.baseName, rarity = item.rarity, base_stats = pickStats(calcBase), slots = { } }
	local jewelIndex = { }
	for i, nodeId in ipairs(sortedJewelSockets()) do jewelIndex[nodeId] = i end
	if item.type == "Flask" then
		-- 플라스크: 효과는 '사용 중'일 때만 → 지금 플라스크도 켠 상태 vs 이 플라스크를 켠 상태로 비교.
		-- 같은 베이스가 장착된 칸이 있으면 그 칸만, 없으면 모든 플라스크 칸.
		local cand, same = { }, { }
		for n = 1, 5 do
			local sname = "Flask " .. n
			local slot = itemsTab.slots[sname]
			if slot and itemsTab:IsItemValidForSlot(item, sname) then
				local cur = itemsTab.items[slot.selItemId]
				cand[#cand + 1] = sname
				if cur and cur.baseName == item.baseName then same[#same + 1] = sname end
			end
		end
		for _, sname in ipairs(#same > 0 and same or cand) do
			local slot = itemsTab.slots[sname]
			local cur = itemsTab.items[slot.selItemId]
			local base = res.base_stats
			if cur and not slot.active then base = pickStats(calcFunc({ toggleFlask = cur })) end
			local stats = pickStats(calcFunc({ repSlotName = sname, repItem = item,
				toggleFlask = (not slot.active) and item or nil }))
			res.slots[#res.slots + 1] = {
				slot = sname, label = slot.label or sname, replacing = cur and cur.name or "",
				stats = stats, base = base, flask = true,
			}
		end
		res.note = "flask"
		return res
	end
	for slotName, slot in pairs(itemsTab.slots) do
		if itemsTab:IsItemValidForSlot(item, slotName) and not slot.inactive
			and (not slot.weaponSet or slot.weaponSet == (itemsTab.activeItemSet.useSecondWeaponSet and 2 or 1))
			and slot.shown() and not slotName:find("^Flask") then
			local selItem = itemsTab.items[slot.selItemId]
			local output
			local function heavyBase(it) return it and it.baseName and (it.baseName:find("Cluster Jewel") or it.baseName == "Timeless Jewel") end
			if slot.nodeId and (heavyBase(selItem) or item.baseName == "Timeless Jewel") and not item.clusterJewel then
				-- 트리 모양/노드를 바꾸는 주얼(클러스터·무궁한 주얼)이 걸리면 빠른 계산은 틀림 → 실제로 바꿔 끼고 계산
				if not item.id then itemsTab:AddItem(item, true) end
				local oldId = slot.selItemId
				local before = allocIds()
				slot:SetSelItemId(item.id)
				build.buildFlag = true
				frame()
				output = build.calcsTab.mainOutput
				local picked = pickStats(output)
				slot:SetSelItemId(oldId)
				reallocIds(before)
				build.buildFlag = true
				frame()
				output = picked
			else
				output = pickStats(calcFunc({ repSlotName = slotName, repItem = item }))
			end
			res.slots[#res.slots + 1] = {
				slot = slotName,
				label = slot.label or slotName,
				replacing = selItem and selItem.name or "",
				stats = output,
				jewel = slot.nodeId and jewelIndex[slot.nodeId] or nil,
				abyss = slotName:find("Abyssal") and true or nil,
			}
		end
	end
	if item.id then
		-- 계산용으로 잠깐 넣은 아이템 제거 (빌드 아이템 목록에 남기지 않음)
		itemsTab.items[item.id] = nil
		for i, id in ipairs(itemsTab.itemOrderList) do
			if id == item.id then table.remove(itemsTab.itemOrderList, i) break end
		end
	end
	if item.clusterJewel then res.note = "cluster" end
	-- 슬롯 순서 고정 (pairs 순서는 매번 달라서 무기 2 가 먼저 나오기도 함): 무기 1 → 무기 2 → … → 반지 1 → 반지 2 …
	local order = { ["Weapon 1"] = 1, ["Weapon 2"] = 2, ["Weapon 1 Swap"] = 3, ["Weapon 2 Swap"] = 4, ["Helmet"] = 5,
		["Body Armour"] = 6, ["Gloves"] = 7, ["Boots"] = 8, ["Amulet"] = 9, ["Ring 1"] = 10, ["Ring 2"] = 11,
		["Ring 3"] = 12, ["Belt"] = 13 }
	table.sort(res.slots, function(a, b)
		local ra, rb = order[a.slot] or 100 + (a.jewel or 0), order[b.slot] or 100 + (b.jewel or 0)
		if ra ~= rb then return ra < rb end
		return tostring(a.slot) < tostring(b.slot)
	end)
	return res
end

-- '왜 이렇게 바뀌나': 옵션 줄을 하나씩 빼고 다시 계산해서 줄마다 기여도를 구한다.
--  새 아이템 줄: (새 아이템 전체) - (그 줄 뺀 새 아이템)  → 이 줄이 주는 것
--  지금 장비 줄: (지금 상태) - (그 줄 뺀 지금 장비)      → 바꾸면 잃는 것
local EXPLAIN_KEYS = { "FullDPS", "CombinedDPS", "TotalEHP", "Life", "EnergyShield", "Mana",
	-- 재생 / RF 등 지속 피해를 뺀 순 회복 (PoB Net* 는 지속 피해가 있을 때만 있음)
	"LifeRegenRecovery", "EnergyShieldRegenRecovery", "NetLifeRegen", "NetEnergyShieldRegen", "NetManaRegen" }
local function explainPick(o)
	local t = { }
	for _, k in ipairs(EXPLAIN_KEYS) do
		local v = o and o[k]
		if type(v) == "number" and v == v then t[k] = (v == math.huge) and 1e300 or v end
	end
	if es_minion_in_main then
		local md = minionDPS(o)
		if md then t.CombinedDPS = (t.CombinedDPS or 0) + md end
	end
	return t
end
local function explainLines(item, slotName, calcFunc, ref, sign)
	local out = { }
	local raw = item:BuildRaw()
	for _, listName in ipairs({ "enchantModLines", "implicitModLines", "explicitModLines" }) do
		for i, ml in ipairs(item[listName] or { }) do
			local ok, st = pcall(function()
				local clone = new("Item", raw)
				table.remove(clone[listName], i)
				clone:BuildAndParseRaw()
				clone:BuildModList()
				return explainPick(calcFunc({ repSlotName = slotName, repItem = clone }))
			end)
			if ok and st then
				local d = { }
				for _, k in ipairs(EXPLAIN_KEYS) do
					local a, b = ref[k], st[k]
					if a and b and a < 1e299 and b < 1e299 then d[k] = sign * (a - b) end
				end
				out[#out + 1] = {
					list = listName, idx = i,
					line = ml.line, kind = listName:gsub("ModLines", ""), crafted = ml.crafted or nil,
					unsupported = (ml.extra or (ml.modList and #ml.modList == 0)) and true or nil, d = d,
				}
			end
		end
	end
	return out
end

-- '장착템 옵션 끄고 켜기': 지금 슬롯에 낀 아이템에서 spec("explicitModLines:2,implicitModLines:1") 줄을 뺀
-- 상태로 계산. 줄 목록도 같이 돌려줌 (번호 = PoB 목록 안 순서, 다시 부를 때 그대로 씀)
local VARIANT_LISTS = { "enchantModLines", "implicitModLines", "explicitModLines" }
function es_slot_variant(slotName, spec, contrib)
	local itemsTab = build.itemsTab
	local slot = itemsTab.slots[slotName]
	if not slot then return { error = "no slot " .. tostring(slotName) } end
	local cur = itemsTab.items[slot.selItemId]
	if not cur then return { error = "empty" } end
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local res = { slot = slotName, name = cur.name, base_name = cur.baseName, rarity = cur.rarity,
		quality = cur.quality, base = pickStats(calcBase), lines = { } }
	local off, any = { }, false
	for l, i in tostring(spec or ""):gmatch("(%a+):(%d+)") do
		off[l .. ":" .. i] = true
		any = true
	end
	for _, listName in ipairs(VARIANT_LISTS) do
		for i, ml in ipairs(cur[listName] or { }) do
			if cur:CheckModLineVariant(ml) and ml.line and ml.line ~= "" then
				res.lines[#res.lines + 1] = {
					list = listName, idx = i, line = ml.line, kind = (listName:gsub("ModLines", "")),
					crafted = ml.crafted or nil, fractured = ml.fractured or nil,
					unsupported = (ml.extra or (ml.modList and #ml.modList == 0)) and true or nil,
					off = off[listName .. ":" .. i] or nil,
				}
			end
		end
	end
	if contrib then
		-- 줄마다 '이 줄 하나만 빼면 잃는 양' (전부 켠 지금 장비 기준, 왜 이렇게 바뀌나 와 같은 계산)
		local by = { }
		for _, e in ipairs(explainLines(cur, slotName, calcFunc, explainPick(calcBase), 1)) do
			by[e.list .. ":" .. e.idx] = e.d
		end
		for _, l in ipairs(res.lines) do l.d = by[l.list .. ":" .. l.idx] end
	end
	if any then
		local clone = new("Item", cur:BuildRaw())
		for _, listName in ipairs(VARIANT_LISTS) do
			local t = clone[listName] or { }
			for i = #t, 1, -1 do
				if off[listName .. ":" .. i] then table.remove(t, i) end
			end
		end
		clone:BuildAndParseRaw()
		clone:BuildModList()
		res.stats = pickStats(calcFunc({ repSlotName = slotName, repItem = clone }))
	else
		res.stats = res.base
	end
	return res
end

function es_explain_item(itemText, slotName)
	local item = new("Item", itemText)
	if not item.base then return { error = "item could not be parsed" } end
	item:BuildModList()
	local itemsTab = build.itemsTab
	local slot = itemsTab.slots[slotName]
	if not slot then return { error = "no slot " .. tostring(slotName) } end
	local calcFunc, calcBase = build.calcsTab:GetMiscCalculator()
	local base = explainPick(calcBase)
	local newSt = explainPick(calcFunc({ repSlotName = slotName, repItem = item }))
	local res = { slot = slotName, base = base, new = newSt,
		new_lines = explainLines(item, slotName, calcFunc, newSt, 1), old_lines = { } }
	local cur = itemsTab.items[slot.selItemId]
	if cur then
		res.old_name = cur.name
		res.old_lines = explainLines(cur, slotName, calcFunc, base, 1)
	end
	return res
end
