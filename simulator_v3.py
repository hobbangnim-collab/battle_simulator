import csv
import random
from dataclasses import dataclass, field
from pathlib import Path


MAX_ROUNDS = 8
APTITUDE_SCALE = {"S": 1.20, "A": 1.10, "B": 1.00, "C": 0.90}
CONTROL_STATUSES = {"stun", "silence", "disarm", "taunt", "fear", "heal_lock", "vulnerable", "broken"}
DAMAGE_TYPES = {"weapon", "strategy"}
ADVANCEMENT_LEVELS = {
    "단무지": 0,
    "1돌": 1,
    "2돌": 2,
    "3돌": 3,
    "4돌": 4,
    "풀돌": 5,
    "컬풀돌": 6,
}
STATUS_ALIASES = {
    "기절": "stun",
    "허망": "silence",
    "무장해제": "disarm",
    "도발": "taunt",
    "치료금지": "heal_lock",
    "피습": "vulnerable",
    "파괴": "broken",
    "공포": "fear",
}


@dataclass(frozen=True)
class Tactic:
    name: str
    phase: str
    type: str
    rate: float
    power: float
    target: str
    turns: int
    status: str = ""
    caster_role: str = ""
    target_side: str = ""
    target_role: str = ""
    stack_rule: str = "highest"
    effect_key: str = ""


@dataclass(frozen=True)
class EquipmentSkill:
    equipment_name: str
    slot: str
    tactic: Tactic


@dataclass
class TimedValue:
    value: float
    turns: int
    source: str
    damage_type: str = "all"
    key: str = ""


@dataclass
class Unit:
    name: str
    base_force: int
    base_intellect: int
    base_command: int
    base_speed: int
    base_charm: int
    base_politics: int
    max_troops: int
    troops: int
    troop_type: str
    aptitude: str
    cavalry_aptitude: str
    spear_aptitude: str
    bow_aptitude: str
    shield_aptitude: str
    siege_aptitude: str
    morale: float
    tactics: list[Tactic]
    side: str = ""
    role: str = ""
    advancement: str = "단무지"
    equipment: dict[str, str] = field(default_factory=dict)
    force: float = 0
    intellect: float = 0
    command: float = 0
    speed: float = 0
    charm: float = 0
    politics: float = 0
    dealt_mods: list[TimedValue] = field(default_factory=list)
    taken_mods: list[TimedValue] = field(default_factory=list)
    stat_mods: list[TimedValue] = field(default_factory=list)
    counter_power: float = 0.0
    counter_turns: int = 0
    burn_power: float = 0.0
    burn_turns: int = 0
    weakness: int = 0
    basic_attacks: int = 1
    statuses: dict[str, int] = field(default_factory=dict)
    taunt_target: str = ""

    @property
    def alive(self):
        return self.troops > 0

    @property
    def troop_ratio(self):
        return max(0.15, self.troops / max(1, self.max_troops))

    @property
    def morale_damage_loss(self):
        if self.morale >= 100:
            return 0.0
        return min(0.55, max(0.0, (100.0 - self.morale) * 0.0071))

    @property
    def morale_damage_scale(self):
        return 1.0 - self.morale_damage_loss


@dataclass
class BattleResult:
    winner: str
    rounds: int
    left_a: int
    left_b: int
    log_sections: dict[str, list[str]] = field(default_factory=dict)

    @property
    def log(self):
        lines = []
        for title, section in self.log_sections.items():
            lines.append(f"=== {title} ===")
            lines.extend(section)
        return lines


def load_tactics(path):
    tactics = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            def value(english, korean, default=""):
                return row.get(english, row.get(korean, default))

            name = value("name", "전법명")
            tactics[name] = Tactic(
                name=name,
                phase=value("phase", "발동시점"),
                type=value("type", "효과유형"),
                rate=float(value("rate", "발동률")),
                power=float(value("power", "계수")),
                target=value("target", "대상"),
                turns=int(value("turns", "지속턴")),
                status=value("status", "상태"),
                caster_role=value("caster_role", "발동조건역할"),
                target_side=value("target_side", "대상진영"),
                target_role=value("target_role", "대상역할"),
                stack_rule=value("stack_rule", "중첩규칙", "highest") or "highest",
                effect_key=value("effect_key", "효과키"),
            )
    return tactics


def load_equipment_skills(path):
    equipment_skills = {}
    path = Path(path)
    if not path.exists():
        return equipment_skills

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            def value(english, korean, default=""):
                return row.get(english, row.get(korean, default))

            equipment_name = value("equipment_name", "장비명")
            slot = value("slot", "장비종류")
            skill_name = value("skill_name", "스킬명")
            if not equipment_name or not slot or not skill_name:
                continue

            tactic = Tactic(
                name=f"{equipment_name} - {skill_name}",
                phase=value("phase", "발동시점"),
                type=value("type", "효과유형"),
                rate=float(value("rate", "발동률", 1)),
                power=float(value("power", "계수", 0)),
                target=value("target", "대상", "self"),
                turns=int(value("turns", "지속턴", 0)),
                status=value("status", "상태"),
                caster_role=value("caster_role", "발동조건역할"),
                target_side=value("target_side", "대상진영"),
                target_role=value("target_role", "대상역할"),
                stack_rule=value("stack_rule", "중첩규칙", "highest") or "highest",
                effect_key=value("effect_key", "효과키"),
            )
            equipment_skills[equipment_name] = EquipmentSkill(equipment_name=equipment_name, slot=slot, tactic=tactic)
    return equipment_skills


def load_generals(path, tactics):
    generals = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            def value(english, korean, default=""):
                return row.get(english, row.get(korean, default))

            tactic_list = []
            for name in [value("tactic1", "전법1"), value("tactic2", "전법2"), value("tactic3", "전법3")]:
                if name and name in tactics:
                    tactic_list.append(tactics[name])
            name = value("name", "장수")
            default_aptitude = value("aptitude", "적성", "B")
            level = int(value("level", "레벨", 1))
            level_gain = max(0, level - 1)

            def stat_value(stat, korean):
                direct = value(stat, korean, "")
                if direct != "":
                    return int(float(direct))
                base = float(value(f"base_{stat}", f"기본{korean}", 1))
                growth = float(value(f"{stat}_growth", f"{korean}성장", 0))
                bonus = float(row.get(f"{korean}투자", row.get(f"{korean}보너스", row.get(f"{stat}_bonus", 0))))
                return int(base + growth * level_gain + bonus)

            generals[name] = Unit(
                name=name,
                base_force=stat_value("force", "무력"),
                base_intellect=stat_value("intellect", "지력"),
                base_command=stat_value("command", "통솔"),
                base_speed=stat_value("speed", "속도"),
                base_charm=stat_value("charm", "매력"),
                base_politics=stat_value("politics", "정치"),
                max_troops=int(value("troops", "병력", 10000)),
                troops=int(value("troops", "병력", 10000)),
                troop_type=value("troop_type", "기본병종", "창병"),
                aptitude=default_aptitude,
                cavalry_aptitude=value("cavalry_aptitude", "기병적성", default_aptitude),
                spear_aptitude=value("spear_aptitude", "창병적성", default_aptitude),
                bow_aptitude=value("bow_aptitude", "궁병적성", default_aptitude),
                shield_aptitude=value("shield_aptitude", "방패병적성", default_aptitude),
                siege_aptitude=value("siege_aptitude", "병기적성", default_aptitude),
                morale=100.0,
                tactics=tactic_list,
                role=value("role", "역할", ""),
                advancement=value("advancement", "돌파", "단무지"),
            )
    return generals


def aptitude_for_troop(unit):
    return {
        "기병": unit.cavalry_aptitude,
        "창병": unit.spear_aptitude,
        "궁병": unit.bow_aptitude,
        "방패병": unit.shield_aptitude,
        "병기": unit.siege_aptitude,
    }.get(unit.troop_type, unit.aptitude)


def clone_unit(unit, side, role=""):
    return Unit(
        name=unit.name,
        base_force=unit.base_force,
        base_intellect=unit.base_intellect,
        base_command=unit.base_command,
        base_speed=unit.base_speed,
        base_charm=unit.base_charm,
        base_politics=unit.base_politics,
        max_troops=unit.max_troops,
        troops=unit.max_troops,
        troop_type=unit.troop_type,
        aptitude=unit.aptitude,
        cavalry_aptitude=unit.cavalry_aptitude,
        spear_aptitude=unit.spear_aptitude,
        bow_aptitude=unit.bow_aptitude,
        shield_aptitude=unit.shield_aptitude,
        siege_aptitude=unit.siege_aptitude,
        morale=100.0,
        tactics=unit.tactics,
        side=side,
        role=role or unit.role,
        advancement=unit.advancement,
        equipment=dict(unit.equipment),
    )


def alive_units(army):
    return [unit for unit in army if unit.alive]


def total_troops(army):
    return sum(unit.troops for unit in army if unit.alive)


def unit_label(unit):
    return f"[{unit.name}]"


def stronger_value(new_value, old_value):
    if new_value < 0 or old_value < 0:
        return abs(new_value) > abs(old_value)
    return new_value > old_value


def add_mod(unit, bucket, source, value, turns, damage_type="all", stack_rule="highest", effect_key=""):
    key = effect_key or source
    same = [mod for mod in bucket if mod.key == key and mod.damage_type == damage_type]
    new_mod = TimedValue(value=value, turns=turns, source=source, damage_type=damage_type, key=key)

    if stack_rule == "stack" or not same:
        bucket.append(new_mod)
        return new_mod, "applied"

    current = same[0]
    if stack_rule == "unique":
        return current, "ignored"
    if stack_rule == "refresh":
        current.value = value
        current.turns = max(current.turns, turns)
        current.source = source
        return current, "refreshed"
    if stack_rule == "highest":
        if stronger_value(value, current.value):
            current.value = value
            current.source = source
            current.turns = max(current.turns, turns)
            return current, "replaced"
        current.turns = max(current.turns, turns)
        return current, "kept"

    bucket.append(new_mod)
    return new_mod, "applied"


def sum_mod(mods, damage_type):
    return sum(mod.value for mod in mods if mod.damage_type in {"all", damage_type})


def decay_mods(mods):
    kept = []
    expired = []
    for mod in mods:
        mod.turns -= 1
        if mod.turns > 0:
            kept.append(mod)
        else:
            expired.append(mod)
    return kept, expired


def pick_targets(tactic, actor, own, enemy, rng):
    if tactic.target == "self":
        return [actor]

    if tactic.target_side or tactic.target_role:
        pool = own if tactic.target_side in {"self", "ally", "아군", "자신"} else enemy
        units = alive_units(pool)
        if tactic.target_role:
            if tactic.target_role in {"부장", "부장전체"}:
                units = [unit for unit in units if unit.role.startswith("부장")]
            elif tactic.target_role not in {"전체", "all"}:
                units = [unit for unit in units if unit.role == tactic.target_role]
        if not units:
            return []
        if tactic.target in {"enemy_all", "ally_all"} or tactic.target_role in {"전체", "부장", "부장전체"}:
            return units
        rng.shuffle(units)
        if tactic.target.endswith("_2"):
            return units[:2]
        return units[:1]

    if tactic.target == "ally_all":
        return alive_units(own)
    if tactic.target == "ally_2":
        units = alive_units(own)
        rng.shuffle(units)
        return units[:2]
    if tactic.target == "ally_1":
        units = alive_units(own)
        return [min(units, key=lambda unit: unit.troops / max(1, unit.max_troops))] if units else []

    enemies = alive_units(enemy)
    if not enemies:
        return []
    if actor.taunt_target:
        taunter = next((unit for unit in enemies if unit.name == actor.taunt_target and unit.alive), None)
        if taunter:
            return [taunter]
    if tactic.target == "enemy_all":
        return enemies
    rng.shuffle(enemies)
    if tactic.target == "enemy_2":
        return enemies[:2]
    return enemies[:1]


def apply_damage(target, amount):
    before = target.troops
    target.troops = max(0, target.troops - max(0, amount))
    return before - target.troops


def apply_heal(target, amount):
    before = target.troops
    target.troops = min(target.max_troops, target.troops + max(0, amount))
    return target.troops - before


def add_status(target, status, turns, source, log):
    if not status or turns <= 0:
        return
    status = STATUS_ALIASES.get(status, status)
    target.statuses[status] = max(target.statuses.get(status, 0), turns)
    labels = {
        "stun": "기절",
        "silence": "허망",
        "disarm": "무장해제",
        "taunt": "도발",
        "heal_lock": "치료 금지",
        "vulnerable": "피습",
        "broken": "파괴",
        "fear": "공포",
    }
    log.append(f"{unit_label(target)} [{source}] 효과로 {labels.get(status, status)} 상태를 획득합니다.")


def damage_amount(attacker, defender, power, damage_type, rng):
    dealt_mod = sum_mod(attacker.dealt_mods, damage_type)
    taken_mod = sum_mod(defender.taken_mods, damage_type)
    if damage_type == "weapon":
        attack_stat = attacker.force
        defense_stat = defender.command
        base = attack_stat * 12.0 - defense_stat * 5.0
        floor = 65
    else:
        attack_stat = attacker.intellect
        defense_stat = defender.intellect * 3.8 + defender.command * 1.8
        base = attack_stat * 12.0 - defense_stat
        floor = 60

    weakness_amp = min(0.45, defender.weakness * 0.045)
    scale = (1.0 + dealt_mod) * (1.0 + taken_mod + weakness_amp)
    scale *= attacker.troop_ratio * attacker.morale_damage_scale
    return int(max(floor, base) * power * scale * rng.uniform(0.90, 1.10))


def heal_amount(caster, power, rng):
    base = caster.intellect * 8.0 + caster.command * 2.5
    return int(base * power * caster.troop_ratio * rng.uniform(0.92, 1.08))


def deal_damage(attacker, target, own, enemy, power, damage_type, rng, log, source, trigger_hooks=True):
    if trigger_hooks:
        trigger_event("before_damage", attacker, own, enemy, rng, log)
    dealt = apply_damage(target, damage_amount(attacker, target, power, damage_type, rng))
    damage_name = "책략 피해" if damage_type == "strategy" else "피해"
    log.append(f"{unit_label(attacker)}이(가) {unit_label(target)}에게 {source} {damage_name}를 입혀 {dealt} 병력을 잃었습니다.")
    if trigger_hooks:
        trigger_event("after_damage", attacker, own, enemy, rng, log)
        trigger_event("when_damaged", target, enemy, own, rng, log)
    return dealt


def log_damage_mod(unit, mod, verb, log):
    damage_name = {"weapon": "무기", "strategy": "책략", "all": "전체"}.get(mod.damage_type, mod.damage_type)
    direction = "증가" if mod.value >= 0 else "감소"
    log.append(f"{unit_label(unit)} {verb} {damage_name} 피해가 {abs(mod.value):.2%} {direction}합니다.")


def log_stack_result(unit, source, result, log):
    if result == "ignored":
        log.append(f"{unit_label(unit)} [{source}] 효과는 이미 적용 중이라 중복 적용되지 않습니다.")
    elif result == "refreshed":
        log.append(f"{unit_label(unit)} [{source}] 효과 지속 시간이 갱신됩니다.")
    elif result == "kept":
        log.append(f"{unit_label(unit)} [{source}]보다 강한 같은 계열 효과가 유지됩니다.")
    elif result == "replaced":
        log.append(f"{unit_label(unit)} [{source}] 효과가 더 강해 교체 적용됩니다.")


def apply_tactic(actor, own, enemy, tactic, rng, log):
    if tactic.caster_role and actor.role != tactic.caster_role:
        log.append(f"{unit_label(actor)} [{tactic.name}]은(는) {tactic.caster_role} 전용이라 발동하지 않습니다.")
        return
    if tactic.phase in {"active", "assault", "action_start"} and "stun" in actor.statuses:
        log.append(f"{unit_label(actor)} 기절 상태라 [{tactic.name}]이(가) 발동하지 않습니다.")
        return
    if tactic.phase == "active" and "silence" in actor.statuses:
        log.append(f"{unit_label(actor)} 허망 상태라 [{tactic.name}]이(가) 발동하지 않습니다.")
        return
    if rng.random() > tactic.rate:
        log.append(f"{unit_label(actor)} [{tactic.name}]이(가) 확률 때문에 발동하지 않습니다.")
        return

    targets = pick_targets(tactic, actor, own, enemy, rng)
    if not targets:
        return
    log.append(f"{unit_label(actor)} [{tactic.name}] 전법 발동")

    if tactic.type == "physical_damage":
        for target in targets:
            deal_damage(
                actor,
                target,
                own,
                enemy,
                tactic.power,
                "weapon",
                rng,
                log,
                tactic.name,
                trigger_hooks=tactic.phase not in {"before_damage", "after_damage", "when_damaged"},
            )
            add_status(target, tactic.status, tactic.turns, tactic.name, log)
    elif tactic.type == "strategy_damage":
        for target in targets:
            deal_damage(
                actor,
                target,
                own,
                enemy,
                tactic.power,
                "strategy",
                rng,
                log,
                tactic.name,
                trigger_hooks=tactic.phase not in {"before_damage", "after_damage", "when_damaged"},
            )
            add_status(target, tactic.status, max(1, tactic.turns), tactic.name, log)
    elif tactic.type == "heal":
        for target in targets:
            if "heal_lock" in target.statuses:
                log.append(f"{unit_label(target)} 치료 금지 상태라 회복하지 못합니다.")
                continue
            healed = apply_heal(target, heal_amount(actor, tactic.power, rng))
            log.append(f"{unit_label(actor)}이(가) {unit_label(target)}의 {healed} 병력을 회복했습니다.")
            if tactic.phase not in {"after_heal", "when_healed"}:
                trigger_event("after_heal", actor, own, enemy, rng, log)
                target_own = own if target in own else enemy
                target_enemy = enemy if target in own else own
                trigger_event("when_healed", target, target_own, target_enemy, rng, log)
    elif tactic.type == "damage_reduce":
        for target in targets:
            mod, result = add_mod(
                target,
                target.taken_mods,
                tactic.name,
                -tactic.power,
                max(1, tactic.turns),
                "all",
                tactic.stack_rule,
                tactic.effect_key or f"taken:{tactic.status or 'all'}",
            )
            if result in {"applied", "replaced", "refreshed"}:
                log_damage_mod(target, mod, "받는", log)
            log_stack_result(target, tactic.name, result, log)
    elif tactic.type == "split_damage_reduce":
        damage_type = tactic.status if tactic.status in DAMAGE_TYPES else "all"
        for target in targets:
            mod, result = add_mod(
                target,
                target.taken_mods,
                tactic.name,
                -tactic.power,
                max(1, tactic.turns),
                damage_type,
                tactic.stack_rule,
                tactic.effect_key or f"taken:{damage_type}",
            )
            if result in {"applied", "replaced", "refreshed"}:
                log_damage_mod(target, mod, "받는", log)
            log_stack_result(target, tactic.name, result, log)
    elif tactic.type == "damage_amp":
        damage_type = tactic.status if tactic.status in DAMAGE_TYPES else "all"
        for target in targets:
            mod, result = add_mod(
                target,
                target.dealt_mods,
                tactic.name,
                tactic.power,
                max(1, tactic.turns),
                damage_type,
                tactic.stack_rule,
                tactic.effect_key or f"dealt:{damage_type}",
            )
            if result in {"applied", "replaced", "refreshed"}:
                log_damage_mod(target, mod, "주는", log)
            log_stack_result(target, tactic.name, result, log)
    elif tactic.type == "attribute_buff":
        for target in targets:
            target.command *= 1.0 + tactic.power
            target.speed *= 1.0 + tactic.power
            log.append(f"{unit_label(target)} 통솔/속도가 {tactic.power:.2%} 증가합니다.")
    elif tactic.type == "speed_buff":
        for target in targets:
            target.speed *= 1.0 + tactic.power
            log.append(f"{unit_label(target)} 속도가 {tactic.power:.2%} 증가합니다.")
    elif tactic.type == "speed_down":
        for target in targets:
            target.speed *= max(0.05, 1.0 - tactic.power)
            log.append(f"{unit_label(target)} 속도가 {tactic.power:.2%} 감소합니다.")
            if tactic.status:
                choices = [STATUS_ALIASES.get(item.strip(), item.strip()) for item in tactic.status.split("|") if item.strip()]
                if choices:
                    add_status(target, rng.choice(choices), max(1, tactic.turns), tactic.name, log)
    elif tactic.type == "stat_down":
        for target in targets:
            loss = tactic.power + target.weakness * 0.012
            target.force *= 1.0 - loss
            target.intellect *= 1.0 - loss
            target.command *= 1.0 - loss
            target.speed *= 1.0 - loss
            log.append(f"{unit_label(target)} 허점 현재 횟수 {target.weakness}")
            log.append(f"{unit_label(target)} 무력/지력/통솔/속도가 {loss:.2%} 감소합니다.")
    elif tactic.type == "counter":
        for target in targets:
            target.counter_power = max(target.counter_power, tactic.power)
            target.counter_turns = max(target.counter_turns, tactic.turns)
            log.append(f"{unit_label(target)} 반격 상태를 획득합니다.")
    elif tactic.type == "burn":
        for target in targets:
            target.burn_power = max(target.burn_power, tactic.power)
            target.burn_turns = max(target.burn_turns, tactic.turns)
            log.append(f"{unit_label(target)} 화상 상태가 부여됩니다.")
    elif tactic.type == "weakness":
        for target in targets:
            target.weakness += max(1, int(tactic.power))
            log.append(f"{unit_label(target)}이(가) {target.weakness}개의 허점 효과를 획득합니다.")
    elif tactic.type == "distribute_weakness":
        total = max(1, int(tactic.power))
        alive_targets = targets[:]
        for _ in range(total):
            target = rng.choice(alive_targets)
            target.weakness += 1
        for target in alive_targets:
            log.append(f"{unit_label(target)} 허점 현재 횟수 {target.weakness}")
    elif tactic.type == "extra_basic":
        actor.basic_attacks = max(actor.basic_attacks, 1 + int(tactic.power))
        log.append(f"{unit_label(actor)} 연격 효과가 발동되었습니다.")
    elif tactic.type in {"silence", "disarm", "taunt"}:
        for target in targets:
            add_status(target, tactic.type, tactic.turns, tactic.name, log)
            if tactic.type == "taunt":
                target.taunt_target = actor.name
    elif tactic.type == "clear_control":
        for target in targets:
            before = set(target.statuses)
            target.statuses = {k: v for k, v in target.statuses.items() if k not in CONTROL_STATUSES}
            if before != set(target.statuses):
                log.append(f"{unit_label(target)} 제어 상태가 해제되었습니다.")


def trigger_event(event, actor, own, enemy, rng, log):
    for tactic in actor.tactics:
        if tactic.phase == event:
            apply_tactic(actor, own, enemy, tactic, rng, log)


def trigger_army_event(event, a, b, rng, log):
    for own, enemy in [(a, b), (b, a)]:
        for unit in alive_units(own):
            trigger_event(event, unit, own, enemy, rng, log)


def prepare_army(army, side_name, log):
    log.append(f"[{side_name}] 부대 준비")
    for unit in army:
        unit.aptitude = aptitude_for_troop(unit)
        aptitude_scale = APTITUDE_SCALE.get(unit.aptitude, 1.0)
        unit.force = unit.base_force * aptitude_scale
        unit.intellect = unit.base_intellect * aptitude_scale
        unit.command = unit.base_command * aptitude_scale
        unit.speed = unit.base_speed * aptitude_scale
        unit.charm = unit.base_charm * aptitude_scale
        unit.politics = unit.base_politics * aptitude_scale
        role_text = f" {unit.role}" if unit.role else ""
        log.append(f"{unit_label(unit)}{role_text}: {unit.troop_type} 적성 {unit.aptitude}, 속성이 기준의 {aptitude_scale:.0%}로 조정됩니다.")
        if unit.morale_damage_loss > 0:
            log.append(f"{unit_label(unit)} 부대의 현재 사기 {unit.morale:.2f}, 주는 피해가 {unit.morale_damage_loss:.2%} 감소합니다.")
        else:
            log.append(f"{unit_label(unit)} 부대의 현재 사기 {unit.morale:.2f}, 주는 피해는 변하지 않습니다.")
        advancement_level = ADVANCEMENT_LEVELS.get(unit.advancement, 0)
        if advancement_level > 0:
            dealt_value = advancement_level * 0.02
            taken_value = -advancement_level * 0.02
            add_mod(unit, unit.dealt_mods, "돌파", dealt_value, MAX_ROUNDS + 1, "all", "unique", "advancement:dealt")
            add_mod(unit, unit.taken_mods, "돌파", taken_value, MAX_ROUNDS + 1, "all", "unique", "advancement:taken")
            log.append(
                f"{unit_label(unit)} {unit.advancement}: 주는 피해 {dealt_value:.0%} 증가, 받는 피해 {abs(taken_value):.0%} 감소합니다."
            )


def prebattle(a, b, rng, log):
    for event in ["prepare", "command"]:
        log.append(f"[{event}] 전투 전 효과 처리")
        for own, enemy in [(a, b), (b, a)]:
            for unit in own:
                trigger_event(event, unit, own, enemy, rng, log)


def tick_start_of_action(unit, rng, log):
    if unit.burn_turns > 0 and unit.alive:
        amount = int(max(60, unit.max_troops * 0.018) * unit.burn_power * rng.uniform(0.9, 1.1))
        dealt = apply_damage(unit, amount)
        log.append(f"{unit_label(unit)} 화상 피해로 {dealt} 병력을 잃었습니다.")
        unit.burn_turns -= 1
        if unit.burn_turns <= 0:
            unit.burn_power = 0

    unit.dealt_mods, expired = decay_mods(unit.dealt_mods)
    for mod in expired:
        log.append(f"{unit_label(unit)} [{mod.source}] 효과가 사라졌습니다.")
    unit.taken_mods, expired = decay_mods(unit.taken_mods)
    for mod in expired:
        log.append(f"{unit_label(unit)} [{mod.source}] 효과가 사라졌습니다.")

    if unit.counter_turns > 0:
        unit.counter_turns -= 1
        if unit.counter_turns <= 0:
            unit.counter_power = 0

    expired_statuses = []
    for status, turns in list(unit.statuses.items()):
        if turns <= 1:
            expired_statuses.append(status)
        else:
            unit.statuses[status] = turns - 1
    for status in expired_statuses:
        unit.statuses.pop(status, None)
        if status == "taunt":
            unit.taunt_target = ""


def basic_attack(actor, own, enemy, rng, log):
    if "stun" in actor.statuses:
        log.append(f"{unit_label(actor)} 기절 상태라 일반 공격을 시전하지 못합니다.")
        return
    if "disarm" in actor.statuses:
        log.append(f"{unit_label(actor)} 무장해제 상태라 일반 공격을 시전하지 못합니다.")
        return

    for index in range(actor.basic_attacks):
        if not alive_units(enemy):
            return
        trigger_event("before_basic", actor, own, enemy, rng, log)
        target = pick_targets(Tactic("", "", "", 0, 0, "enemy_1", 0), actor, own, enemy, rng)[0]
        suffix = "" if actor.basic_attacks == 1 else f" {index + 1}회"
        log.append(f"{unit_label(actor)}이(가) {unit_label(target)}에게 일반 공격을 시전합니다.{suffix}")
        deal_damage(actor, target, own, enemy, 1.0, "weapon", rng, log, "일반 공격")
        if target.alive and target.counter_power > 0:
            deal_damage(target, actor, enemy, own, target.counter_power, "weapon", rng, log, "반격")
        trigger_event("after_basic", actor, own, enemy, rng, log)


def action_turn(actor, own, enemy, rng, log):
    log.append(f"{unit_label(actor)} 행동 턴")
    log.append(f"{unit_label(actor)} 행동 시작")
    tick_start_of_action(actor, rng, log)
    trigger_event("action_start", actor, own, enemy, rng, log)
    for tactic in actor.tactics:
        if tactic.phase == "active":
            apply_tactic(actor, own, enemy, tactic, rng, log)
    basic_attack(actor, own, enemy, rng, log)
    for tactic in actor.tactics:
        if tactic.phase == "assault":
            apply_tactic(actor, own, enemy, tactic, rng, log)


def simulate_battle(army_a, army_b, seed=None, keep_log=True):
    rng = random.Random(seed)
    roles = ["주장", "부장1", "부장2"]
    a = [clone_unit(unit, "A", roles[index] if index < len(roles) else "") for index, unit in enumerate(army_a)]
    b = [clone_unit(unit, "B", roles[index] if index < len(roles) else "") for index, unit in enumerate(army_b)]
    sections = {"준비": []}

    prepare_army(a, "A", sections["준비"])
    prepare_army(b, "B", sections["준비"])
    prebattle(a, b, rng, sections["준비"])

    for round_no in range(1, MAX_ROUNDS + 1):
        log = sections.setdefault(f"턴{round_no}", [])
        log.append(f"[{round_no}번째 턴]")
        trigger_army_event("round_start", a, b, rng, log)
        actors = [(unit.speed + rng.random(), "A", unit) for unit in alive_units(a)]
        actors += [(unit.speed + rng.random(), "B", unit) for unit in alive_units(b)]
        actors.sort(reverse=True, key=lambda item: item[0])

        for _, side, actor in actors:
            if not actor.alive:
                continue
            own = a if side == "A" else b
            enemy = b if side == "A" else a
            if not alive_units(enemy):
                break
            action_turn(actor, own, enemy, rng, log)

        trigger_army_event("round_end", a, b, rng, log)
        if not alive_units(a) or not alive_units(b):
            return finish_result(a, b, round_no, sections if keep_log else {})

    return finish_result(a, b, MAX_ROUNDS, sections if keep_log else {})


def finish_result(a, b, rounds, sections):
    left_a = total_troops(a)
    left_b = total_troops(b)
    if left_a > left_b:
        winner = "A"
    elif left_b > left_a:
        winner = "B"
    else:
        winner = "Draw"
    return BattleResult(winner=winner, rounds=rounds, left_a=left_a, left_b=left_b, log_sections=sections)


def run_batch(army_a, army_b, count, seed=1):
    return [simulate_battle(army_a, army_b, seed=seed + index, keep_log=False) for index in range(count)]
