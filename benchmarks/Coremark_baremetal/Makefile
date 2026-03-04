# Makefile for CoreMark on RV64IM
#
# Target: RV64IM (with M extension for hardware mul/div)
# Clock: 50MHz (adjust EE_TICKS_PER_SEC in core_portme.c if different)

CROSS_COMPILE ?= riscv64-unknown-elf-
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

# Architecture flags - RV64IM with Zicsr extension
ARCH_FLAGS = -march=rv64i_zicsr -mabi=lp64

# CoreMark configuration
ITERATIONS ?= 0
TOTAL_DATA_SIZE ?= 2000

# Compiler flags string for reporting
FLAGS_STR = "-O2 -march=rv64i_zicsr -mabi=lp64 -fno-common -funroll-loops"

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
CODE_FLAGS += -mcmodel=medany

# Combined CFLAGS
CFLAGS  = $(ARCH_FLAGS)
CFLAGS += $(OPT_FLAGS) $(WARN_FLAGS) $(CODE_FLAGS)
CFLAGS += $(CM_CFLAGS)

ASFLAGS = $(ARCH_FLAGS) -Wa,-march=rv64i_zicsr

# Linker flags
LDFLAGS  = $(ARCH_FLAGS)
LDFLAGS += -T$(LDSCRIPT)
LDFLAGS += -Wl,--gc-sections
LDFLAGS += -Wl,-Map=$(TARGET).map
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

# Generate Verilog memory file (32-bit words for compatibility)
verilog: $(TARGET).bin
	@echo "Generating Verilog memory file..."
	@hexdump -v -e '1/4 "%08x\n"' $(TARGET).bin > $(TARGET).mem
	@echo "Generated $(TARGET).mem"
	@wc -l $(TARGET).mem

size: $(TARGET).elf
	@echo ""
	@echo "=== Memory Usage ==="
	$(SIZE) $(TARGET).elf

dump: $(TARGET).elf
	$(OBJDUMP) -d -S $< > $(TARGET).dump

clean:
	rm -f *.o $(TARGET).elf $(TARGET).hex $(TARGET).bin $(TARGET).mem $(TARGET).dump $(TARGET).map

help:
	@echo "CoreMark for RV64I"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build ELF, HEX, and BIN files"
	@echo "  verilog  - Generate .mem file for Verilog simulation"
	@echo "  size     - Show memory usage"
	@echo "  dump     - Generate disassembly"
	@echo "  clean    - Remove build files"
