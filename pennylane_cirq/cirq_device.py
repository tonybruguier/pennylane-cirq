# Copyright 2019 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Base device class for PennyLane-Cirq
===========================

**Module name:** :mod:`pennylane_cirq.cirq_device`

.. currentmodule:: pennylane_cirq.cirq_device

An abstract base class for constructing Cirq devices for PennyLane.
This abstract base class will not be used by the user.

Classes
-------

.. autosummary::
   CirqDevice

Code details
~~~~~~~~~~~~
"""
import cirq
import numpy as np
import pennylane as qml
from pennylane import QubitDevice
from pennylane.operation import Operation

from ._version import __version__
from .cirq_interface import CirqOperation, unitary_matrix_gate


class CirqDevice(QubitDevice):
    """Abstract base device for PennyLane-Cirq.

    Args:
        wires (int): the number of modes to initialize the device in
        shots (int): Number of circuit evaluations/random samples used
            to estimate expectation values of observables. Shots need to be >= 1.
        qubits (List[cirq.Qubit]): a list of Cirq qubits that are used
            as wires. The wire number corresponds to the index in the list.
            By default, an array of `cirq.LineQubit` instances is created.
    """

    name = "Cirq Abstract PennyLane plugin baseclass"
    pennylane_requires = ">=0.6.0"
    version = __version__
    author = "Johannes Jakob Meyer"
    _capabilities = {"model": "qubit", "tensor_observables": False, "inverse_operations": True}

    short_name = "cirq.base_device"

    def __init__(self, wires, shots, analytic, qubits=None):
        super().__init__(wires, shots, analytic)

        self.circuit = None

        if qubits:
            if wires != len(qubits):
                raise qml.DeviceError(
                    "The number of given qubits and the specified number of wires have to match. Got {} wires and {} qubits.".format(
                        wires, len(qubits)
                    )
                )

            self.qubits = qubits
        else:
            self.qubits = [cirq.LineQubit(wire) for wire in range(wires)]

        # Add inverse operations
        self._inverse_operation_map = {}
        for key in self._operation_map:
            if not self._operation_map[key]:
                continue

            # We have to use a new CirqOperation instance because .inv() acts in-place
            inverted_operation = CirqOperation(self._operation_map[key].parametrization)
            inverted_operation.inv()

            self._inverse_operation_map[key + Operation.string_for_inverse] = inverted_operation

        self._complete_operation_map = {**self._operation_map, **self._inverse_operation_map}

    _operation_map = {
        "BasisState": None,
        "QubitStateVector": None,
        "QubitUnitary": CirqOperation(unitary_matrix_gate),
        "PauliX": CirqOperation(lambda: cirq.X),
        "PauliY": CirqOperation(lambda: cirq.Y),
        "PauliZ": CirqOperation(lambda: cirq.Z),
        "Hadamard": CirqOperation(lambda: cirq.H),
        "S": CirqOperation(lambda: cirq.S),
        "T": CirqOperation(lambda: cirq.T),
        "CNOT": CirqOperation(lambda: cirq.CNOT),
        "SWAP": CirqOperation(lambda: cirq.SWAP),
        "CZ": CirqOperation(lambda: cirq.CZ),
        "PhaseShift": CirqOperation(lambda phi: cirq.ZPowGate(exponent=phi / np.pi)),
        "RX": CirqOperation(lambda phi: cirq.Rx(phi)),
        "RY": CirqOperation(lambda phi: cirq.Ry(phi)),
        "RZ": CirqOperation(lambda phi: cirq.Rz(phi)),
        "Rot": CirqOperation(lambda a, b, c: [cirq.Rz(a), cirq.Ry(b), cirq.Rz(c)]),
        "CRX": CirqOperation(lambda phi: cirq.ControlledGate(cirq.Rx(phi))),
        "CRY": CirqOperation(lambda phi: cirq.ControlledGate(cirq.Ry(phi))),
        "CRZ": CirqOperation(lambda phi: cirq.ControlledGate(cirq.Rz(phi))),
        "CRot": CirqOperation(
            lambda a, b, c: [
                cirq.ControlledGate(cirq.Rz(a)),
                cirq.ControlledGate(cirq.Ry(b)),
                cirq.ControlledGate(cirq.Rz(c)),
            ]
        ),
        "CSWAP": CirqOperation(lambda: cirq.CSWAP),
        "Toffoli": CirqOperation(lambda: cirq.TOFFOLI),
    }

    _observable_map = {
        "PauliX": None,
        "PauliY": None,
        "PauliZ": None,
        "Hadamard": None,
        "Hermitian": None,
        "Identity": None,
    }

    def reset(self):
        super().reset()

        self.circuit = cirq.Circuit()

    @property
    def observables(self):
        return set(self._observable_map.keys())

    @property
    def operations(self):
        return set(self._operation_map.keys())

    def pre_apply(self):
        self.reset()

    def apply_basis_state(self, basis_state_operation):
        pass

    def apply_qubit_state_vector(self, qubit_state_vector_operation):
        pass

    def apply(self, operations, rotations=None, **kwargs):
        rotations = rotations or []

        for i, operation in enumerate(operations):
            if operation.name == "BasisState":
                if i > 0:
                    raise qml.DeviceError(
                        "The operation BasisState is only supported at the beginning of a circuit."
                    )

                self.apply_basis_state(operation)
            elif operation.name == "QubitStateVector":
                if i > 0:
                    raise qml.DeviceError(
                        "The operation QubitStateVector is only supported at the beginning of a circuit."
                    )

                self.apply_qubit_state_vector(operation)
            else:
                cirq_operation = self._complete_operation_map[operation.name]

                # If command is None do nothing
                if cirq_operation:
                    cirq_operation.parametrize(*operation.parameters)

                    self.circuit.append(cirq_operation.apply(*[self.qubits[wire] for wire in operation.wires]))

        # TODO: get pre rotated state here

        # TODO: Remove duplicate code
        # Diagonalize the given observables
        for operation in rotations:
            cirq_operation = self._complete_operation_map[operation]

            # If command is None do nothing
            if cirq_operation:
                cirq_operation.parametrize(*operation.parameters)

                self.circuit.append(cirq_operation.apply(*[self.qubits[wire] for wire in operation.wires]))
