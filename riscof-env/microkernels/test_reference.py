"""Tests for arithmetic corner semantics and the independent decoded-image oracle."""
import struct
import unittest
from reference import DONE, START, STOP, execute, muldiv


class ReferenceTests(unittest.TestCase):
    def test_signed_division_truncates_toward_zero(self):
        self.assertEqual(muldiv(-17, 3, 4, 32), 0xfffffffb)
        self.assertEqual(muldiv(-17, 3, 6, 32), 0xfffffffe)
        self.assertEqual(muldiv(17, -3, 4, 64), (1 << 64)-5)
        self.assertEqual(muldiv(17, -3, 6, 64), 2)

    def test_zero_divisor_and_overflow(self):
        for bits in (32,64):
            mask=(1 << bits)-1
            for op in (4,5): self.assertEqual(muldiv(17,0,op,bits),mask)
            for op in (6,7): self.assertEqual(muldiv(17,0,op,bits),17)
            self.assertEqual(muldiv(1 << (bits-1),mask,4,bits),1 << (bits-1))
            self.assertEqual(muldiv(1 << (bits-1),mask,6,bits),0)

    def test_high_multiplication(self):
        self.assertEqual(muldiv(-1,2,1,32),0xffffffff)
        self.assertEqual(muldiv(-1,-1,1,32),0)
        self.assertEqual(muldiv(-1,0xffffffff,2,32),0xffffffff)
        self.assertEqual(muldiv(0xffffffff,0xffffffff,3,32),0xfffffffe)

    def test_known_instruction_count_and_branch(self):
        # addi x1,zero,2; START; addi x1,x1,-1; bne x1,zero,-4; STOP; DONE
        words=[0x00200093,START,0xfff08093,0xfe009ee3,STOP,DONE]
        for bits in (32,64):
            r=execute(struct.pack('<6I',*words),bits)
            self.assertEqual(r['retired'],4)
            self.assertEqual(r['branch'],2)
            self.assertEqual(r['taken'],1)
            self.assertEqual(r['check_hash'],r['roi_hash'])


if __name__=='__main__': unittest.main()
