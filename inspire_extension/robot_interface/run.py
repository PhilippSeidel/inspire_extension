import argparse
import traceback

from .inspire_interface import openSerial, write6, read6
from incar_networking.robot_interface import IncarRobotInterface, ROBOT_STATE_CHANNEL

class InspireHand:
    def __init__(self, serial_port: str = '/dev/ttyUSB0'):
        self.serial = openSerial(serial_port, 115200)

    def move_joints(self, joint_positions: list[float]):
        try:
            command = [
                int(joint_positions[0]),
                int(joint_positions[1]),
                int(joint_positions[2]),
                int(joint_positions[3]),
                int(joint_positions[4]),
                int(joint_positions[5])
            ]
            write6(self.serial, 1, 'angleSet', command)
        except:
            traceback.print_exc()
    
    def set_state(self, interface: IncarRobotInterface):
        try:
            currentAngles = read6(self.serial, 1, 'angleAct')
            currentForces = read6(self.serial, 1, 'forceAct')
            interface.set_robot_state("hand", joint_pos=currentAngles, joint_effort=currentForces)
            interface.publish_state()
        except:
            traceback.print_exc()

    def set_state_and_publish(self, interface: IncarRobotInterface):
        self.set_state(interface)
        interface.publish_state()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="INCAR teleoperation of the Inspire hand")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port for the Inspire hand")
    robot = InspireHand(serial_port=parser.parse_args().port)
    interface = IncarRobotInterface(
        0.01,
        command_hooks = {
            "right.commands.hand.inspire": robot.move_joints
        },
        loop_callbacks = [
            robot.set_state_and_publish
        ]
    )
    
    state_channel = interface._rtc.data_channels[ROBOT_STATE_CHANNEL]
    
    @state_channel.on("open")
    def publish_initial_state():
        robot.set_state(interface)
    
    interface.start("127.0.0.1")