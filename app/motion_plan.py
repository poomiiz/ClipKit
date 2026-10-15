"""Shared ownership rules for rendered motion and existing subtitle events."""
from video_edit import VideoEditError


ROLES = {"normal", "emphasis", "caption", "second", "title"}


def ownership(motion: dict) -> dict:
    """Read old media conservatively; explicit recipes must declare what they replace."""
    if "ownership" not in motion:
        return {"mode": "legacy_full_card", "targets": [], "caption_policy": "hide"}
    value = motion["ownership"]
    if not isinstance(value, dict) or set(value) != {"mode", "targets", "caption_policy"}:
        raise VideoEditError("motion ownership requires mode, targets and caption_policy")
    mode, targets, policy = value["mode"], value["targets"], value["caption_policy"]
    if mode not in ("decorate", "replace", "full_card") or policy not in ("preserve", "replace", "hide"):
        raise VideoEditError("motion ownership mode or caption policy is invalid")
    if not isinstance(targets, list):
        raise VideoEditError("motion ownership targets must be an array")
    seen = set()
    caption = False
    for target in targets:
        if (not isinstance(target, dict) or set(target) != {"cue_id", "roles"}
                or not isinstance(target["cue_id"], str) or not target["cue_id"].strip()
                or not isinstance(target["roles"], list) or not target["roles"]
                or any(not isinstance(role, str) or role not in ROLES for role in target["roles"])):
            raise VideoEditError("motion target requires an actual cue_id and subtitle roles")
        for role in target["roles"]:
            key = target["cue_id"], role
            if key in seen:
                raise VideoEditError("motion ownership target is duplicated")
            seen.add(key)
            caption |= role == "caption"
    if mode == "decorate" and (targets or policy != "preserve"):
        raise VideoEditError("decoration must preserve all subtitles and captions")
    if mode == "replace" and (not targets or policy == "hide" or caption != (policy == "replace")):
        raise VideoEditError("replacement must name its roles and declare caption replacement explicitly")
    if mode == "full_card" and targets:
        raise VideoEditError("full_card owns its interval; use replace for individual cue roles")
    return {"mode": mode, "targets": [{"cue_id": t["cue_id"], "roles": list(t["roles"])} for t in targets],
            "caption_policy": policy}


def hides(motion: dict, *, role: str | None, cue_id: str | None) -> bool:
    policy = ownership(motion)
    if policy["mode"] == "legacy_full_card":
        return True
    if role not in ROLES:
        raise VideoEditError("explicit motion ownership needs the subtitle role")
    if policy["mode"] == "decorate":
        return False
    if role == "caption" and policy["caption_policy"] == "preserve":
        return False
    if policy["mode"] == "full_card":
        return True
    return any(target["cue_id"] == cue_id and role in target["roles"] for target in policy["targets"])
