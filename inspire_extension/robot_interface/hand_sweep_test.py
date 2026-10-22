import time
from .inspire_interface import openSerial, readRegister, writeRegister, write6, regdict

PORT = '/dev/ttyUSB0'
HAND_ID = 1
DOF_NAMES = ['little', 'ring', 'middle', 'index', 'thumb_bend', 'thumb_rot']
OPEN, CLOSED = 1000, 0
TOL = 50          # how close to the target counts as "reached"
TIMEOUT = 3.0     # seconds allowed per move
POLL = 0.1        # seconds between readbacks
RETRIES = 1       # extra attempts (after clearing errors) if a move fails


def read_u8(ser, key):
    """Read a 1-byte-per-DOF register (errCode, statusCode, temp)."""
    raw = readRegister(ser, HAND_ID, regdict[key], 6, mute=True)
    return list(raw[:6]) if raw and len(raw) >= 6 else None


def read_i16(ser, key):
    """Read a 2-byte-per-DOF signed register quietly (no console spam)."""
    raw = readRegister(ser, HAND_ID, regdict[key], 12, mute=True)
    if not raw or len(raw) < 12:
        return None
    vals = [raw[2 * i] | (raw[2 * i + 1] << 8) for i in range(6)]
    return [v - 65536 if v > 32767 else v for v in vals]


def dump(ser, label):
    print(f'--- {label} ---')
    for key in ['angleAct', 'forceAct', 'speedSet', 'forceSet']:
        print(f'{key:<10}', read_i16(ser, key))
    for key in ['errCode', 'statusCode', 'temp']:
        print(f'{key:<10}', read_u8(ser, key))


def clear_errors(ser):
    writeRegister(ser, HAND_ID, regdict['clearErr'], 1, [1])
    time.sleep(0.1)


def move_and_wait(ser, dof, target):
    """Command one DOF (others -1 = untouched) and poll until reached or timeout."""
    cmd = [-1] * 6
    cmd[dof] = target
    write6(ser, HAND_ID, 'angleSet', cmd)

    statuses, angle = set(), None
    t0 = time.time()
    while time.time() - t0 < TIMEOUT:
        time.sleep(POLL)
        angles = read_i16(ser, 'angleAct')
        status = read_u8(ser, 'statusCode')
        if angles is None or status is None:
            continue
        angle = angles[dof]
        statuses.add(status[dof])
        if abs(angle - target) <= TOL:
            return True, angle, statuses, time.time() - t0
    return False, angle, statuses, time.time() - t0


def main():
    ser = openSerial(PORT, 115200)

    dump(ser, 'before')          # capture fault state before anything is cleared
    clear_errors(ser)
    write6(ser, HAND_ID, 'speedSet', [1000] * 6)
    write6(ser, HAND_ID, 'forceSet', [1000] * 6)

    print('\nOpening hand...')
    write6(ser, HAND_ID, 'angleSet', [OPEN] * 6)
    time.sleep(2.0)

    results = {}
    for dof, name in enumerate(DOF_NAMES):
        dof_ok = True
        for target in (CLOSED, OPEN):
            for attempt in range(RETRIES + 1):
                ok, angle, statuses, dt = move_and_wait(ser, dof, target)
                tag = '' if attempt == 0 else f' (retry {attempt})'
                print(f'{name:<11} -> {target:>4}: {"OK  " if ok else "FAIL"} '
                      f'angle={angle} statuses={sorted(statuses)} t={dt:.1f}s{tag}')
                if ok:
                    break
                print(f'{"":<11}    err={read_u8(ser, "errCode")} -> clearing errors')
                clear_errors(ser)
            dof_ok &= ok
        results[name] = dof_ok

    write6(ser, HAND_ID, 'angleSet', [OPEN] * 6)
    time.sleep(1.0)
    dump(ser, 'after')

    print('\n=== summary ===')
    for name, ok in results.items():
        print(f'{name:<11} {"OK" if ok else "STUCK"}')

    ser.close()


if __name__ == '__main__':
    main()