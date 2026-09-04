from .services import active_alerts_for_user


def alert_count(request):
    if request.user.is_authenticated:
        return {"active_alert_count": active_alerts_for_user(request.user).count()}
    return {"active_alert_count": 0}
