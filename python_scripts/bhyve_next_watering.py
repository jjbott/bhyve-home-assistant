# pylint: disable=undefined-variable
now = dt_util.now()

zone_entity_id = data.get("entity_id")

if not zone_entity_id:
    raise Exception("entity_id is required to execute this script")

zone = hass.states.get(zone_entity_id)

if not zone:
    raise Exception("Entity with id {} does not exist".format(zone_entity_id))

device_name = zone.attributes.get("device_name")
zone_name = zone.attributes.get("zone_name")

if not device_name:
    raise Exception(
        "Could not find zone's device name on entity {}. Is this a BHyve zone switch entity?".format(
            zone_entity_id
        )
    )

if not zone_name:
    zone_id = zone_entity_id.split('.')[1]
    logger.warn(f"{zone_entity_id} is unnamed. Using '{zone_id}'");
    zone_name = zone_id

logger.info("updating next_watering for zone: ({}: {})".format(zone_name, zone))

next_watering_entity = f"sensor.{zone_name}_next_watering".replace(" ", "_").replace("-", "_").lower()
next_watering_attrs = {"friendly_name": f"{zone_name} next watering"}

rain_delay_finishing_entity = f"sensor.{device_name}_rain_delay_finishing".replace(
    " ", "_"
).replace("-", "_").replace("#", "_").replace("__", "_").lower()
rain_delay_finishing_attrs = {"friendly_name": f"{device_name} rain delay finishing"}

rain_delay = hass.states.get(f"switch.{device_name}_rain_delay")

if zone.state == "unavailable":
    hass.states.set(next_watering_entity, "Unavailable", next_watering_attrs)
    hass.states.set(
        rain_delay_finishing_entity, "Unavailable", rain_delay_finishing_attrs
    )
else:
    delay_finishes_at = None
    
    next_watering = now + datetime.timedelta(days= 366) 

    if rain_delay.state == "on":
        started_at = dt_util.as_timestamp(rain_delay.attributes.get("started_at"))
        delay_seconds = rain_delay.attributes.get("delay") * 3600
        delay_finishes_at = dt_util.as_local(
            dt_util.utc_from_timestamp(started_at + delay_seconds)
        )
        hass.states.set(
            rain_delay_finishing_entity, delay_finishes_at, rain_delay_finishing_attrs
        )
    else:
        hass.states.set(rain_delay_finishing_entity, None, rain_delay_finishing_attrs)

    for program_id in ["a", "b", "c", "e"]:
        program = zone.attributes.get(f"program_{program_id}")
        logger.info("program: %s", program)
        if program is None or program.get("enabled", False) is False:
            continue

        if program.get("is_smart_program"):
            for timestamp in program.get("watering_program", []):
                watering_time = dt_util.parse_datetime(str(timestamp))
                if (watering_time > now) and (watering_time < next_watering) and (
                    delay_finishes_at is None or watering_time > delay_finishes_at
                ):
                    next_watering = watering_time
                    break
        else:
            """ find the next manual watering time """
            """
                Orbit day: `0` is Sunday, `1` is Monday
                Python day: `0` is Monday, `2` is Tuesday
            """

            """
                ************
                    TODO
                ************
            """
            frequency = program.get("frequency", {})
            start_times = program.get("start_times")
            type = frequency.get("type");
            
            if type == "interval":
                interval = frequency.get("interval")
                interval_start = dt_util.as_local(dt_util.parse_datetime(str(frequency.get("interval_start_time"))))
                diff = now.date() - interval_start.date()
                nextDate = interval_start.date() + datetime.timedelta(days= (diff.days / interval) * interval) 
                
                nextTime = datetime.datetime.combine(nextDate, datetime.time(0,0), interval_start.tzinfo)
                while nextTime < now:
                    for start_time in start_times:
                        startTime = time.strptime(start_time, "%H:%M");
                        nextTime = datetime.datetime.combine(nextDate, datetime.time(startTime.tm_hour, startTime.tm_min), interval_start.tzinfo)
                        if nextTime > now:
                            break
                    nextDate = nextDate + datetime.timedelta(days=interval) 
                
                if nextTime < next_watering:
                    next_watering = nextTime
            if type == "days":
                configured_days = program.get("frequency", {}).get("days")
                if configured_days is None:
                    continue
                
                today = now.date()
                sunday = today - datetime.timedelta(days=(today.weekday() + 1))

                nextTime = datetime.datetime.combine(sunday, datetime.time(0,0), now.tzinfo)
                while nextTime < now:
                    for configured_day in configured_days:
                        nextDate = sunday + datetime.timedelta(days=configured_day)
                        for start_time in start_times:
                            startTime = time.strptime(start_time, "%H:%M");
                            nextTime = datetime.datetime.combine(nextDate, datetime.time(startTime.tm_hour, startTime.tm_min), now.tzinfo)
                            if nextTime > now:
                                break
                        if nextTime > now:
                            break
                    sunday = sunday + datetime.timedelta(days=7)
                
                if nextTime < next_watering:
                    next_watering = nextTime
                    
            if type == "odd":
                nextDate = datetime.datetime.combine(now.date(), datetime.time(0,0), now.tzinfo)
                nextTime = nextDate
                while nextTime < now:
                    while nextDate.day % 2 != 1:
                        nextDate = nextDate + datetime.timedelta(days=1)
                    
                    for start_time in start_times:
                        startTime = time.strptime(start_time, "%H:%M");
                        nextTime = datetime.datetime.combine(nextDate, datetime.time(startTime.tm_hour, startTime.tm_min), now.tzinfo)
                        if nextTime > now:
                            break
                            
                    nextDate = nextDate + datetime.timedelta(days=1)
                
                if nextTime < next_watering:
                    next_watering = nextTime
                    
            if type == "even":
                nextDate = datetime.datetime.combine(now.date(), datetime.time(0,0), now.tzinfo)
                nextTime = nextDate
                while nextTime < now:
                    while nextDate.day % 2 != 0:
                        nextDate = nextDate + datetime.timedelta(days=1)
                    
                    for start_time in start_times:
                        startTime = time.strptime(start_time, "%H:%M");
                        nextTime = datetime.datetime.combine(nextDate, datetime.time(startTime.tm_hour, startTime.tm_min), now.tzinfo)
                        if nextTime > now:
                            break
                            
                    nextDate = nextDate + datetime.timedelta(days=1)
                
                if nextTime < next_watering:
                    next_watering = nextTime
                    
    hass.states.set(next_watering_entity, next_watering, next_watering_attrs)
