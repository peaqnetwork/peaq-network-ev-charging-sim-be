import datetime


def _calculate_spent_tokens(charging_period: int, charging_wait_time: int, token_deposit: int) -> (int, int):
    if charging_period > charging_wait_time:
        spent_token = token_deposit
    else:
        spent_token = int((token_deposit - 1) * (charging_period / charging_wait_time) + 1)
    return spent_token, token_deposit - spent_token


def _calculate_energy_consumption(charging_period: datetime.datetime) -> float:
    return charging_period.total_seconds() * 0.2


def calculate_charging_result(charging_start_time: datetime.datetime,
                              charging_end_time: datetime.datetime,
                              charging_wait_time: int,
                              token_deposit: int) -> dict:
    charging_period = charging_end_time - charging_start_time

    spent_token, refund_token = _calculate_spent_tokens(charging_period.total_seconds(), charging_wait_time, token_deposit)
    energy_consumption = _calculate_energy_consumption(charging_period)

    return {
        'spent_token': spent_token,
        'refund_token': refund_token,
        'charging_period': charging_period,
        'energy_consumption': energy_consumption
    }


def calculate_charging_status(start: datetime.datetime, now: datetime.datetime, interval: int) -> float:
    if now < start:
        return 0

    seconds = (now - start).total_seconds()
    if seconds > interval:
        return 100
    return seconds / float(interval) * 100
