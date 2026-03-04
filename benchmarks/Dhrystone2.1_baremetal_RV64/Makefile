# Makefile for Dhrystone on RV64IM (NO DHRYSTONE SOURCE MOD)

CROSS_COMPILE ?= riscv64-unknown-elf-
CC      = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
OBJDUMP = $(CROSS_COMPILE)objdump
SIZE    = $(CROSS_COMPILE)size

TARGET = dhrystone

# Source files
DHRY_SRC = dhry_1.c dhry_2.c
BSP_SRC  = syscalls.c mini_libc.c
ASM_SRC  = crt0.S strcmp.S

HDR = dhry.h
LDSCRIPT = linker.ld

# RV64IM architecture flags (M extension for hardware mul/div)
ARCH_FLAGS = -march=rv64im_zicsr -mabi=lp64

# include current dir so that ./sys/times.h shadows newlib's one
INC_FLAGS = -I.

# Dhrystone flags
DHRY_CFLAGS  = -std=gnu89
DHRY_CFLAGS += -DTIMES -DNOENUM -DDHRY_ITERS=300000
DHRY_CFLAGS += -DHZ=48611110
DHRY_CFLAGS += -Wno-implicit -Wno-return-type -Wno-builtin-declaration-mismatch

# Optimization
OPT_FLAGS = -O2

WARN_FLAGS = -Wall

CODE_FLAGS  = -fno-common
CODE_FLAGS += -ffunction-sections -fdata-sections
CODE_FLAGS += -ffreestanding
CODE_FLAGS += -mcmodel=medany

CFLAGS  = $(ARCH_FLAGS) $(INC_FLAGS)
CFLAGS += $(OPT_FLAGS) $(WARN_FLAGS) $(CODE_FLAGS) $(DHRY_CFLAGS)

ASFLAGS = $(ARCH_FLAGS) -Wa,-march=rv64im_zicsr

LDFLAGS  = $(ARCH_FLAGS)
LDFLAGS += -T$(LDSCRIPT)
LDFLAGS += -Wl,--gc-sections
LDFLAGS += -Wl,-Map=$(TARGET).map
LDFLAGS += -Wl,--defsym=__stack_size=0x800
LDFLAGS += -Wl,--defsym=__heap_size=0x1000
# IMPORTANT: do not link newlib libc (prevents ROM overflow)
LDFLAGS += -nostdlib -nodefaultlibs

LIBS = -lgcc

DHRY_OBJ = $(DHRY_SRC:.c=.o)
BSP_OBJ  = $(BSP_SRC:.c=.o)
ASM_OBJ  = $(ASM_SRC:.S=.o)
OBJS     = $(ASM_OBJ) $(DHRY_OBJ) $(BSP_OBJ)

.PHONY: all clean dump verilog size

all: $(TARGET).elf $(TARGET).hex $(TARGET).bin size

$(TARGET).elf: $(OBJS) $(LDSCRIPT)
	$(CC) $(LDFLAGS) $(OBJS) $(LIBS) -o $@

%.o: %.c $(HDR)
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.S
	$(CC) $(ASFLAGS) -c $< -o $@

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

verilog: $(TARGET).bin
	@echo "Generating Verilog memory file..."
	@hexdump -v -e '1/4 "%08x\n"' $(TARGET).bin > $(TARGET).mem
	@echo "Generated $(TARGET).mem"
	@wc -l $(TARGET).mem

size: $(TARGET).elf
	@echo ""
	@echo "=== Memory Usage ==="
	$(SIZE) $(TARGET).elf
	@echo ""

dump: $(TARGET).elf
	$(OBJDUMP) -d -S $< > $(TARGET).dump

clean:
	rm -f *.o $(TARGET).elf $(TARGET).hex $(TARGET).bin $(TARGET).mem $(TARGET).dump $(TARGET).map
