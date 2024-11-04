class InstrCounter:
    """Instruction Counter"""
    def __init__(self):
        self.counter = 0

    def step(self):
        self.counter += 1

    def reset(self):
        self.counter = 0

    def set(self, val):
        if int(val) < 0:
            raise ValueError('The instruction counter cannot be negative')
        self.counter = int(val)

    def val(self):
        return self.counter
