"""Small independent RV I/M interpreter for the generated kernels.

This is a functional oracle, not a timing model or a replacement for Sail.
Unsupported instructions and uninitialized loads fail closed.
"""
import struct

MASK64 = (1 << 64) - 1
START, STOP, DONE = (x << 20 | 0x13 for x in (0x701, 0x702, 0x703))


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def digest(h, pc, insn, rd, value):
    return (((h << 7) | (h >> 57)) ^ pc ^ (insn << 1) ^
            value ^ (rd << 56)) & MASK64


def muldiv(a, b, funct3, bits):
    mask = (1 << bits) - 1
    a, b = a & mask, b & mask
    sa, sb = signed(a, bits), signed(b, bits)
    if funct3 == 0:
        return a * b & mask
    if funct3 in (1, 2, 3):
        aa = sa if funct3 in (1, 2) else a
        bb = sb if funct3 == 1 else b
        return (aa * bb >> bits) & mask
    aa, bb = (sa, sb) if funct3 in (4, 6) else (a, b)
    if bb == 0:
        return mask if funct3 in (4, 5) else a
    q = abs(aa) // abs(bb)
    if (aa < 0) != (bb < 0):
        q = -q
    return (q if funct3 in (4, 5) else aa - q * bb) & mask


def execute(binary, xlen, limit=20000000):
    code = struct.unpack('<%dI' % (len(binary) // 4), binary)
    regs, mem, pc = [0] * 32, {}, 0
    mask = (1 << xlen) - 1
    active = checking = False
    counts = dict(retired=0, branch=0, taken=0, jump=0, load=0,
                  store=0, mul=0, div=0, roi_hash=0, check_hash=0)
    markers = []
    for step in range(limit):
        if pc & 3 or pc // 4 >= len(code):
            raise ValueError('invalid PC %#x' % pc)
        ins = code[pc // 4]
        op, rd, f3 = ins & 127, (ins >> 7) & 31, (ins >> 12) & 7
        rs1, rs2, f7 = (ins >> 15) & 31, (ins >> 20) & 31, ins >> 25
        a, b = regs[rs1], regs[rs2]
        nxt, val, writes, taken = pc + 4, 0, False, False
        imm = signed(ins >> 20, 12)
        if op == 0x13:
            if f3 == 0: val = a + imm
            elif f3 == 4: val = a ^ imm
            elif f3 == 7: val = a & imm
            elif f3 == 1: val = a << ((ins >> 20) & (xlen - 1))
            elif f3 == 5: val = a >> ((ins >> 20) & (xlen - 1))
            else: raise ValueError('unsupported immediate instruction')
            writes = True
        elif op in (0x33, 0x3b):
            bits = 32 if op == 0x3b else xlen
            if f7 == 1: val = muldiv(a, b, f3, bits)
            elif f3 == 0: val = a - b if f7 == 32 else a + b
            elif f3 == 4: val = a ^ b
            else: raise ValueError('unsupported register instruction')
            if bits == 32: val = signed(val, 32)
            writes = True
        elif op == 0x37:
            val, writes = signed(ins & 0xfffff000, 32), True
        elif op == 0x17:
            val, writes = pc + signed(ins & 0xfffff000, 32), True
        elif op == 0x03:
            addr, size = (a + imm) & mask, 1 << (f3 & 3)
            val = sum(mem[addr + i] << (8 * i) for i in range(size))
            if f3 < 4: val = signed(val, size * 8)
            writes = True
        elif op == 0x23:
            off = signed(((ins >> 25) << 5) | ((ins >> 7) & 31), 12)
            addr, size = (a + off) & mask, 1 << f3
            for i in range(size): mem[addr + i] = (b >> (8 * i)) & 255
        elif op == 0x63:
            off = signed(((ins >> 31) << 12) | (((ins >> 7) & 1) << 11) |
                         (((ins >> 25) & 63) << 5) | (((ins >> 8) & 15) << 1), 13)
            if f3 == 0: taken = a == b
            elif f3 == 1: taken = a != b
            elif f3 == 4: taken = signed(a, xlen) < signed(b, xlen)
            elif f3 == 5: taken = signed(a, xlen) >= signed(b, xlen)
            elif f3 == 6: taken = a < b
            elif f3 == 7: taken = a >= b
            if taken: nxt = pc + off
        elif op == 0x6f:
            off = signed(((ins >> 31) << 20) | (((ins >> 12) & 255) << 12) |
                         (((ins >> 20) & 1) << 11) | (((ins >> 21) & 1023) << 1), 21)
            nxt, val, writes = pc + off, pc + 4, True
        elif op == 0x67:
            nxt, val, writes = (a + imm) & ~1, pc + 4, True
        else:
            raise ValueError('unsupported instruction %#x at %#x' % (ins, pc))
        val &= mask
        dest = rd if writes and rd else 0
        value = val if dest else 0
        if ins in (START, STOP, DONE):
            markers.append(ins)
            if ins == START: active = checking = True
            elif ins == STOP: active = False
            else:
                assert markers == [START, STOP, DONE]
                return counts
        else:
            if checking:
                counts['check_hash'] = digest(counts['check_hash'], pc, ins, dest, value)
            if active:
                counts['roi_hash'] = digest(counts['roi_hash'], pc, ins, dest, value)
                counts['retired'] += 1
                for key, condition in (
                    ('branch', op == 0x63), ('taken', taken),
                    ('jump', op in (0x6f, 0x67)), ('load', op == 3), ('store', op == 0x23),
                    ('mul', op in (0x33, 0x3b) and f7 == 1 and f3 < 4),
                    ('div', op in (0x33, 0x3b) and f7 == 1 and f3 >= 4)):
                    counts[key] += int(condition)
        if dest: regs[dest] = val
        regs[0] = 0
        pc = nxt & mask
    raise ValueError('reference did not finish')
