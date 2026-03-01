# Makefile for CoreMark on RV32I46F_5SP
#
# Target: RV32I (no FPU, no M extension)
# Clock: 50MHz
# Memory: ROM 64KB @ 0x00000000, RAM 32KB @ 0x10000000

CROSS_COMPILE ?= riscv32-unknown-elf-
CC      = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
OBJDUMP = $(CROSS_COMPILE)objdump
SIZE    = $(CROSS_COMPILE)size

TARGET = coremark

# Source files
CORE_SRC = core_list_join.c core_main.c core_matrix.c core_state.c core_util.c
PORT_SRC = core_portme.c ee_printf.c
ASM_SRC  = crt0.S

LDSCRIPT = linker.ld

# Architecture flags - RV32I with Zicsr extension
ARCH_FLAGS = -march=rv32i_zicsr -mabi=ilp32

# CoreMark configuration
# ITERATIONS: Number of benchmark iterations
#   - Set to 0 for auto-detection (runs ~10 seconds)
#   - For quick testing, use smaller value like 1000
#   - For valid benchmark, must run >= 10 seconds
# TOTAL_DATA_SIZE: 2000 for performance run, 1200 for profile run
ITERATIONS ?= 0
TOTAL_DATA_SIZE ?= 2000

# Compiler flags string for reporting
FLAGS_STR = "-O2 -march=rv32i_zicsr -mabi=ilp32 -fno-common -funroll-loops"

# CoreMark flags
CM_CFLAGS  = -DITERATIONS=$(ITERATIONS)
CM_CFLAGS += -DTOTAL_DATA_SIZE=$(TOTAL_DATA_SIZE)
CM_CFLAGS += -DFLAGS_STR=\"$(FLAGS_STR)\"
CM_CFLAGS += -DPERFORMANCE_RUN=1

# Optimization
OPT_FLAGS = -O2 -funroll-loops

# Warnings
WARN_FLAGS = -Wall

# Code generation flags
CODE_FLAGS  = -fno-common
CODE_FLAGS += -ffunction-sections -fdata-sections
CODE_FLAGS += -ffreestanding
CODE_FLAGS += -fno-builtin

# Combined CFLAGS
CFLAGS  = $(ARCH_FLAGS)
CFLAGS += $(OPT_FLAGS) $(WARN_FLAGS) $(CODE_FLAGS)
CFLAGS += $(CM_CFLAGS)

ASFLAGS = $(ARCH_FLAGS) -Wa,-march=rv32i_zicsr

# Linker flags
LDFLAGS  = $(ARCH_FLAGS)
LDFLAGS += -T$(LDSCRIPT)
LDFLAGS += -Wl,--gc-sections
LDFLAGS += -Wl,-Map=$(TARGET).map
LDFLAGS += -Wl,--defsym=__stack_size=0x1000
LDFLAGS += -Wl,--defsym=__heap_size=0x1000
LDFLAGS += -nostdlib -nodefaultlibs

LIBS = -lgcc

# Object files
CORE_OBJ = $(CORE_SRC:.c=.o)
PORT_OBJ = $(PORT_SRC:.c=.o)
ASM_OBJ  = $(ASM_SRC:.S=.o)
OBJS     = $(ASM_OBJ) $(CORE_OBJ) $(PORT_OBJ)

.PHONY: all clean dump verilog size help

all: $(TARGET).elf $(TARGET).hex $(TARGET).bin size

$(TARGET).elf: $(OBJS) $(LDSCRIPT)
	$(CC) $(LDFLAGS) $(OBJS) $(LIBS) -o $@

%.o: %.c coremark.h core_portme.h
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.S
	$(CC) $(ASFLAGS) -c $< -o $@

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

# Generate Verilog memory file
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
	@echo "ROM limit: 64KB (65536 bytes)"
	@echo "RAM limit: 32KB (32768 bytes)"

dump: $(TARGET).elf
	$(OBJDUMP) -d -S $< > $(TARGET).dump

clean:
	rm -f *.o $(TARGET).elf $(TARGET).hex $(TARGET).bin $(TARGET).mem $(TARGET).dump $(TARGET).map

help:
	@echo "CoreMark for RV32I46F_5SP"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build ELF, HEX, and BIN files"
	@echo "  verilog  - Generate .mem file for Verilog simulation"
	@echo "  size     - Show memory usage"
	@echo "  dump     - Generate disassembly"
	@echo "  clean    - Remove build files"
	@echo ""
	@echo "Variables:"
	@echo "  ITERATIONS=N       - Set iteration count (0=auto, default)"
	@echo "  TOTAL_DATA_SIZE=N  - Data size (2000=perf, 1200=profile)"
	@echo ""
	@echo "Example:"
	@echo "  make ITERATIONS=1000    # Quick test with 1000 iterations"
	@echo "  make verilog            # Generate memory file"
