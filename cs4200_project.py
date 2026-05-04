MASK32 = 0xFFFFFFFF
REG_SIZE = 32

# ------------------------------------------------------------
# 32-bit helpers
# ------------------------------------------------------------


def u32(x):
    return x & MASK32


def s32(x):
    x &= MASK32
    return x if x < 0x80000000 else x - 0x100000000


def sign_extend(value, bits):
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def get_bits(x, hi, lo):
    mask = (1 << (hi - lo + 1)) - 1
    return (x >> lo) & mask


# ------------------------------------------------------------
# Immediate generators
# ------------------------------------------------------------


def imm_i(instr):
    return sign_extend(get_bits(instr, 31, 20), 12)


def imm_s(instr):
    imm_11_5 = get_bits(instr, 31, 25)
    imm_4_0 = get_bits(instr, 11, 7)

    return sign_extend(((imm_11_5 << 5) | imm_4_0), 12)


def imm_b(instr):
    imm_12 = get_bits(instr, 31, 31)
    imm_11 = get_bits(instr, 7, 7)
    imm_10_5 = get_bits(instr, 30, 25)
    imm_4_1 = get_bits(instr, 11, 8)

    imm = (imm_12 << 12) | (imm_11 << 11) | (imm_10_5 << 5) | (imm_4_1 << 1)

    return sign_extend(imm, 13)


def imm_u(instr):
    return get_bits(instr, 31, 12) << 12


def imm_j(instr):
    imm_20 = get_bits(instr, 31, 31)
    imm_19_12 = get_bits(instr, 19, 12)
    imm_11 = get_bits(instr, 20, 20)
    imm_10_1 = get_bits(instr, 30, 21)

    imm = (imm_20 << 20) | (imm_19_12 << 12) | (imm_11 << 11) | (imm_10_1 << 1)

    return sign_extend(imm, 21)


# ------------------------------------------------------------
# Decode + Control
# ------------------------------------------------------------


def decode(instr):
    d = {}
    d["instr"] = instr
    d["opcode"] = get_bits(instr, 6, 0)
    d["rd"] = get_bits(instr, 11, 7)
    d["funct3"] = get_bits(instr, 14, 12)
    d["rs1"] = get_bits(instr, 19, 15)
    d["rs2"] = get_bits(instr, 24, 20)
    d["funct7"] = get_bits(instr, 31, 25)

    d["imm_I"] = imm_i(instr)
    d["imm_S"] = imm_s(instr)
    d["imm_B"] = imm_b(instr)
    d["imm_U"] = imm_u(instr)
    d["imm_J"] = imm_j(instr)
    return d


def main_control(d):
    c = {
        "RegWrite": 0,
        "MemRead": 0,
        "MemWrite": 0,
        "MemToReg": 0,
        "ALUSrc": 0,
        "Branch": 0,
        "Jump": 0,
        "JumpReg": 0,
        "ALUOp": "ADDR",
        "ImmSel": None,
        "BrType": None,
        "IsNOP": 0,
    }

    opcode = d["opcode"]
    f3 = d["funct3"]

    match opcode:
        case 0x33:
            c["RegWrite"] = 1
            c["ALUOp"] = "R"
        case 0x13:
            c["RegWrite"] = 1
            c["ALUSrc"] = 1
            c["ALUOp"] = "I"
            c["ImmSel"] = "I"
        case 0x03:
            c["RegWrite"] = 1
            c["MemRead"] = 1
            c["MemToReg"] = 1
            c["ALUSrc"] = 1
            c["ImmSel"] = "I"
        case 0x23:
            c["MemWrite"] = 1
            c["ALUSrc"] = 1
            c["ImmSel"] = "S"
        case 0x63:
            c["Branch"] = 1
            c["ALUOp"] = "Branch"
            c["ImmSel"] = "B"

            match f3:
                case 0b000:
                    c["BrType"] = "beq"
                case 0b001:
                    c["BrType"] = "bne"
                case 0b100:
                    c["BrType"] = "blt"
                case 0b101:
                    c["BrType"] = "bge"
                case 0b110:
                    c["BrType"] = "bltu"
                case 0b111:
                    c["BrType"] = "bgeu"
        case 0x6F:
            c["RegWrite"] = 1
            c["Jump"] = 1
            c["ImmSel"] = "J"
        case 0x67:
            c["RegWrite"] = 1
            c["JumpReg"] = 1
            c["ALUSrc"] = 1
            c["ImmSel"] = "I"
        case 0x37:
            c["RegWrite"] = 1
            c["ImmSel"] = "U"
        case 0x17:
            c["ALUSrc"] = 1
            c["ImmSel"] = "U"

    if d["instr"] == 0:
        c["IsNOP"] = 1

    return c


def select_imm(d, c):
    """TODO: select immediate based on c['ImmSel'] else return 0."""
    result = 0

    match c["ImmSel"]:
        case "I":
            result = d["imm_I"]
        case "S":
            result = d["imm_S"]
        case "B":
            result = d["imm_B"]
        case "U":
            result = d["imm_U"]
        case "J":
            result = d["imm_J"]

    return result


# ------------------------------------------------------------
# ALU control + ALU
# ------------------------------------------------------------


def alu_control(c, d):
    ALUOp = c["ALUOp"]
    f3 = d["funct3"]
    f7 = d["funct7"]

    result = "ADD"

    if ALUOp == "R":
        if f3 == 0b000 and f7 == 0b0000000:
            result = "ADD"
        elif f3 == 0b000 and f7 == 0b0100000:
            result = "SUB"
        elif f3 == 0b111 and f7 == 0b0000000:
            result = "AND"
        elif f3 == 0b110 and f7 == 0b0000000:
            result = "OR"
        elif f3 == 0b100 and f7 == 0b0000000:
            result = "XOR"
        elif f3 == 0b001 and f7 == 0b0000000:
            result = "SLL"
        elif f3 == 0b101 and f7 == 0b0000000:
            result = "SRL"
        elif f3 == 0b101 and f7 == 0b0100000:
            result = "SRA"
        elif f3 == 0b010 and f7 == 0b0000000:
            result = "SLT"
        elif f3 == 0b011 and f7 == 0b0000000:
            result = "SLTU"
        elif f3 == 0b000 and f7 == 0b0000001:
            result = "MUL"
        elif f3 == 0b001 and f7 == 0b0000001:
            result = "MULH"
        elif f3 == 0b011 and f7 == 0b0000001:
            result = "MULHU"
        elif f3 == 0b010 and f7 == 0b0000001:
            result = "MULHSU"
        elif f3 == 0b100 and f7 == 0b0000001:
            result = "DIV"
        elif f3 == 0b101 and f7 == 0b0000001:
            result = "DIVU"
        elif f3 == 0b110 and f7 == 0b0000001:
            result = "REM"
        elif f3 == 0b111 and f7 == 0b0000001:
            result = "REMU"
    elif ALUOp == "I":
        if f3 == 0b000:
            result = "ADD"
        elif f3 == 0b111:
            result = "AND"
        elif f3 == 0b110:
            result = "OR"
        elif f3 == 0b100:
            result = "XOR"
        elif f3 == 0b001:
            result = "SLL"
        elif f3 == 0b101 and f7 == 0b0000000:
            result = "SRL"
        elif f3 == 0b101 and f7 == 0b0100000:
            result = "SRA"
        elif f3 == 0b010:
            result = "SLT"
        elif f3 == 0b011:
            result = "SLTU"
    elif ALUOp == "Branch":
        if f3 == 0b000 or f3 == 0b001:
            result = "SUB"
        elif f3 == 0b100 or f3 == 0b101:
            result = "SLT"
        elif f3 == 0b110 or f3 == 0b111:
            result = "SLTU"

    return result


def alu_exec(alu_op, a, b):
    result = 0

    match alu_op:
        case "ADD":
            result = a + b
        case "SUB":
            result = a - b
        case "AND":
            result = a & b
        case "OR":
            result = a | b
        case "XOR":
            result = a ^ b
        case "SLL":
            result = a << b & 0x1F
        case "SRL":
            result = u32(a) >> (b & 0x1F)
        case "SRA":
            result = s32(a) >> (b & 0x1F)
        case "SLT":
            result = a < b
        case "SLTU":
            result = u32(a) < u32(b)
        case "MUL":
            result = a * b
        case "MULH":
            result = (a * b) >> REG_SIZE
        case "MULHU":
            result = (u32(a) * u32(b)) >> REG_SIZE
        case "MULHSU":
            result = (a * u32(b)) >> REG_SIZE
        case "DIV":
            result = -1 if b == 0 else a // b
        case "DIVU":
            result = -1 if b == 0 else u32(a) // u32(b)        
        case "REM":
            test = a//b
            test2 = test * b
            result = -1 if b == 0 else abs((int(a / b) * b) - a)
        case "REMU":
            result = -1 if b == 0 else u32(a) % u32(b)

    return result


def branch_taken(br_type, rs1_val, rs2_val):
    result = False

    match br_type:
        case "beq":
            result = rs1_val == rs2_val
        case "bne":
            result = rs1_val != rs2_val
        case "blt":
            result = rs1_val < rs2_val
        case "bge":
            result = rs1_val >= rs2_val
        case "bltu":
            result = u32(rs1_val) < u32(rs2_val)
        case "bgeu":
            result = u32(rs1_val) >= u32(rs2_val)

    return result


# ------------------------------------------------------------
# Data memory (word aligned)
# ------------------------------------------------------------


def dmem_load_word(dmem, addr):
    if addr % 4 != 0:
        return 0

    return dmem[addr] if addr in dmem else 0


def dmem_store_word(dmem, addr, value):
    if addr % 4 != 0:
        return

    dmem[addr] = value


# ------------------------------------------------------------
# Pipeline registers
# ------------------------------------------------------------


def make_if_id():
    """IF/ID pipeline register bundle."""
    return {"valid": 0, "pc": 0, "instr": 0}


def make_id_ex():
    """ID/EX pipeline register bundle."""
    return {
        "valid": 0,
        "pc": 0,
        "pc_plus4": 0,
        "d": None,
        "c": None,
        "imm": 0,
        "rs1": 0,
        "rs2": 0,
        "rd": 0,
        "rs1_val": 0,
        "rs2_val": 0,
        "alu_op": "ADD",
    }


def make_ex_mem():
    """EX/MEM pipeline register bundle."""
    return {
        "valid": 0,
        "pc_plus4": 0,
        "c": None,
        "d": None,
        "rd": 0,
        "alu_res": 0,
        "rs2_val_fwd": 0,  # store data after forwarding
        "mem_addr": 0,
        "branch_taken": 0,
        "next_pc": 0,
        "wb_val_for_jumps": 0,  # pc+4 for jal/jalr
    }


def make_mem_wb():
    """MEM/WB pipeline register bundle."""
    return {
        "valid": 0,
        "pc_plus4": 0,
        "c": None,
        "d": None,
        "rd": 0,
        "alu_res": 0,
        "mem_data": 0,
        "wb_val_for_jumps": 0,
    }


# ------------------------------------------------------------
# Hazard detection helpers
# ------------------------------------------------------------


def uses_rs1(d):
    if d is None:
        return False
    return d["opcode"] != 0x6F and d["instr"] != 0


def uses_rs2(d):
    if d is None:
        return False
    return d["opcode"] == 0x33 or 0x13 or 0x63


def is_load_c(c):
    if c is None:
        return False
    return c["MemRead"] or c["MemToReg"]


def will_write_c(c):
    if c is None:
        return False
    return c["RegWrite"]


def is_jump_c(c):
    return c["Jump"] or c["JumpReg"]


def forwarding_select(src_reg, ex_mem, mem_wb):
    use_forward = 0
    value = 0

    if will_write_c(ex_mem["c"]) and ex_mem["rd"] == src_reg and not is_load_c(ex_mem["c"]):
        use_forward = 1
        if is_jump_c(ex_mem["c"]):
            value = ex_mem["wb_val_for_jumps"]
        else:
            value = ex_mem["alu_res"]
    elif will_write_c(mem_wb["c"]) and mem_wb["rd"] == src_reg:
        use_forward = 1
        if is_jump_c(mem_wb["c"]):
            value = mem_wb["wb_val_for_jumps"]
        elif is_load_c(mem_wb["c"]):
            value = mem_wb["mem_data"]
        else:
            value = mem_wb["alu_res"]

    return use_forward, value


def load_use_hazard(if_id, id_ex):
    if_id_d = decode(if_id["instr"])
    
    if id_ex["c"] is not None:
        if is_load_c(id_ex["c"]) and will_write_c(id_ex["c"]):
            if uses_rs1(if_id_d):
                return id_ex["rd"] == if_id_d["rs1"]
            elif uses_rs2(if_id_d):
                return id_ex["rd"] == if_id_d["rs2"]

    return False


# ------------------------------------------------------------
# Trace helpers
# ------------------------------------------------------------


def try_mnemonic(d):
    if d is None:
        return "NOP"
    
    f3 = d["funct3"]
    f7 = d["funct7"]
    
    mne = "NOP"
        
    match(d["opcode"]):
        case 0x33:
            if f3 == 0b000 and f7 == 0b0000000:
                mne = "add"
            elif f3 == 0b000 and f7 == 0b0100000:
                mne = "sub"
            elif f3 == 0b111 and f7 == 0b0000000:
                mne = "and"
            elif f3 == 0b110 and f7 == 0b0000000:
                mne = "or"
            elif f3 == 0b100 and f7 == 0b0000000:
                mne = "xor"
            elif f3 == 0b001 and f7 == 0b0000000:
                mne = "sll"
            elif f3 == 0b101 and f7 == 0b0000000:
                mne = "srl"
            elif f3 == 0b101 and f7 == 0b0100000:
                mne = "sra"
            elif f3 == 0b010 and f7 == 0b0000000:
                mne = "slt"
            elif f3 == 0b011 and f7 == 0b0000000:
                mne = "sltu"
            elif f3 == 0b000 and f7 == 0b0000001:
                mne = "mul"
            elif f3 == 0b001 and f7 == 0b0000001:
                mne = "mulh"
            elif f3 == 0b011 and f7 == 0b0000001:
                mne = "mulhu"
            elif f3 == 0b010 and f7 == 0b0000001:
                mne = "mulhsu"
            elif f3 == 0b100 and f7 == 0b0000001:
                mne = "div"
            elif f3 == 0b101 and f7 == 0b0000001:
                mne = "divu"
            elif f3 == 0b110 and f7 == 0b0000001:
                mne = "rem"
            elif f3 == 0b111 and f7 == 0b0000001:
                mne = "remu"

        case 0x13:
            match f3:
                case 0b000:
                    mne = "addi"
                case 0b111:
                    mne = "andi"
                case 0b110:
                    mne = "ori"
                case 0b100:
                    mne = "xori"
                case 0b010:
                    mne = "slti"
                case 0b011:
                    mne = "sltiu"
                case 0b001:
                    mne = "slli"
                case 0b101:
                    if f7 == 0b0000000:
                        mne = "srli"
                    else:
                        mne = "srai"
        case 0x03:
            if f3 == 0b010:
                mne = "lw"
        case 0x23:
            if f3 == 0b010:
                mne = "sw"
        case 0x63:
            match f3:
                case 0b000:
                    mne = "beq"
                case 0b001:
                    mne = "bne"
                case 0b100:
                    mne = "blt"
                case 0b101:
                    mne = "bge"
                case 0b110:
                    mne = "bltu"
                case 0b111:
                    mne = "bgeu"
        case 0x37:
            mne = "lui"
        case 0x17:
            mne = "auipc"
        case 0x6F:
            mne = "jal"
        case 0x67:
            mne = "jalr"
    
    return mne


def trace_cycle(cycle, pc, stall, flush, if_id, id_ex, ex_mem, mem_wb, wb_info):
    return f"cycle={cycle} pc=0x{pc:08x} stall={stall} flush={flush} | IF/ID={try_mnemonic(decode(if_id["instr"]))} | ID/EX={try_mnemonic(id_ex["d"])} | EX/MEM={try_mnemonic(ex_mem["d"])} | MEM/WB={try_mnemonic(mem_wb["d"])}{wb_info}"


# ------------------------------------------------------------
# Program loader + log writers
# ------------------------------------------------------------


def load_imem_from_file(path):
    imem = {}
    pc = 0
    f = open(path, "r", encoding="utf-8")
    for line in f:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.lower().startswith("0x"):
            s = s[2:]
        instr = int(s, 16) & MASK32
        imem[pc] = instr
        pc += 4
    f.close()
    return imem


def write_trace_log(lines, path):
    f = open(path, "w", encoding="utf-8")
    for ln in lines:
        f.write(ln + "\n")
    f.close()


def write_regs_log(regs, path):
    f = open(path, "w", encoding="utf-8")
    for i in range(32):
        f.write("x%-2d = 0x%08X (%d)\n" % (i, u32(regs[i]), s32(regs[i])))
    f.close()


def write_dmem_log(dmem, path):
    f = open(path, "w", encoding="utf-8")
    for a in sorted(dmem.keys()):
        f.write("0x%08X : 0x%08X (%d)\n" % (u32(a), u32(dmem[a]), s32(dmem[a])))
    f.close()


# ------------------------------------------------------------
# Main pipeline simulation loop
# ------------------------------------------------------------


def main():
    imem = load_imem_from_file("hex_inst.txt")

    regs = [0] * 32
    dmem = {}

    pc = 0
    cycle = 0
    max_cycles = 50_000_000

    # Pipeline registers (latched at end of each cycle)
    if_id = make_if_id()
    id_ex = make_id_ex()
    ex_mem = make_ex_mem()
    mem_wb = make_mem_wb()

    trace_lines = []
    fetching_done = False

    while cycle < max_cycles:
        # ------------------------------------------------------------
        # WB stage (commit architectural state)
        # ------------------------------------------------------------
        wb_info = ""
        
        if mem_wb["valid"] and mem_wb["c"]["RegWrite"]:
            wb_val = mem_wb["alu_res"]
            if mem_wb["c"]["MemToReg"]:
                wb_val = mem_wb["mem_data"]
            elif mem_wb["c"]["Jump"] and mem_wb["c"]["RegWrite"]:
                wb_val = mem_wb["wb_val_for_jumps"]

            if mem_wb["rd"] != 0:
                regs[mem_wb["rd"]] = wb_val
            
            regs[0] = 0
            
            wb_info = f" | WB:x{mem_wb["rd"]}<-0x{wb_val:08x}"

        # ------------------------------------------------------------
        # MEM stage (data memory access)
        # ------------------------------------------------------------
        next_mem_wb = make_mem_wb()

        if ex_mem["valid"]:
            next_mem_wb["valid"] = 1
            next_mem_wb["c"] = ex_mem["c"]
            next_mem_wb["d"] = ex_mem["d"]
            next_mem_wb["rd"] = ex_mem["rd"]
            next_mem_wb["alu_res"] = ex_mem["alu_res"]
            next_mem_wb["pc_plus4"] = ex_mem["pc_plus4"]
            next_mem_wb["wb_val_for_jumps"] = ex_mem["wb_val_for_jumps"]
            
            if ex_mem["c"]["MemRead"] and ex_mem["d"]["funct3"] == 0b010:
                next_mem_wb["mem_data"] = dmem_load_word(dmem, ex_mem["mem_addr"])
            
            if ex_mem["c"]["MemWrite"] and ex_mem["d"]["funct3"] == 0b010:
                dmem_store_word(dmem, ex_mem["mem_addr"], ex_mem["rs2_val_fwd"])

        # ------------------------------------------------------------
        # EX stage (ALU + branch/jump resolution + forwarding)
        # ------------------------------------------------------------
        next_ex_mem = make_ex_mem()
        flush = False
        redirect_pc = 0

        if id_ex["valid"]:            
            use_rs1_forward, rs1_forward_val = forwarding_select(id_ex["rs1"], ex_mem, mem_wb)
            rs1_val = rs1_forward_val if use_rs1_forward else id_ex["rs1_val"]
            use_rs2_forward, rs2_forward_val = forwarding_select(id_ex["rs2"], ex_mem, mem_wb)
            rs2_val = rs2_forward_val if use_rs2_forward else id_ex["rs2_val"]

            alu_op = id_ex["alu_op"]
            alu_in2 = id_ex["imm"] if id_ex["c"]["ALUSrc"] else rs2_val
            alu_res = alu_exec(alu_op, rs1_val, alu_in2)
            
            taken = False
            next_pc = id_ex["pc_plus4"]
            if id_ex["c"]["Branch"]:
                taken = branch_taken(id_ex["c"]["BrType"], rs1_val, rs2_val)
                if taken:
                    next_pc = id_ex["pc"] + id_ex["d"]["imm_B"]
            elif is_jump_c(id_ex["c"]):
                taken = True
                if id_ex["c"]["JumpReg"]:
                    next_pc = (rs1_val + id_ex["d"]["imm_I"]) & ~1
                else:
                    next_pc = id_ex["pc"] + id_ex["d"]["imm_J"]
                    
            if taken:
                flush = True
                redirect_pc = next_pc
            
            next_ex_mem["valid"] = 1
            next_ex_mem["c"] = id_ex["c"]
            next_ex_mem["d"] = id_ex["d"]
            next_ex_mem["rd"] = id_ex["rd"]
            next_ex_mem["alu_res"] = alu_res
            next_ex_mem["mem_addr"] = alu_res
            next_ex_mem["rs2_val_fwd"] = rs2_val
            next_ex_mem["pc_plus4"] = id_ex["pc"] + 4
            next_ex_mem["wb_val_for_jumps"] = id_ex["pc_plus4"]
            next_ex_mem["branch_taken"] = taken
            next_ex_mem["next_pc"] = next_pc
        
        # ------------------------------------------------------------
        # ID stage (decode / reg read) + stall insertion
        # ------------------------------------------------------------
        stall = load_use_hazard(if_id, id_ex)
        
        next_id_ex = make_id_ex()

        if not stall and if_id["valid"]:
            next_id_ex["valid"] = 1
            next_id_ex["pc"] = if_id["pc"]
            next_id_ex["pc_plus4"] = if_id["pc"] + 4
            next_id_ex["d"] = decode(if_id["instr"])
            next_id_ex["c"] = main_control(next_id_ex["d"])
            next_id_ex["imm"] = select_imm(next_id_ex["d"], next_id_ex["c"])
            next_id_ex["rs1"] = next_id_ex["d"]["rs1"]
            next_id_ex["rs1_val"] = regs[next_id_ex["rs1"]]
            next_id_ex["rs2"] = next_id_ex["d"]["rs2"]
            next_id_ex["rs2_val"] = regs[next_id_ex["rs2"]]
            next_id_ex["rd"] = next_id_ex["d"]["rd"]
            next_id_ex["alu_op"] = alu_control(next_id_ex["c"], next_id_ex["d"])
            
        if flush:
            next_id_ex["valid"] = 0
        
        if stall:
            id_ex["valid"] = 0
                
        # ------------------------------------------------------------
        # IF stage (fetch) + PC update + stall/flush handling
        # ------------------------------------------------------------
        next_if_id = make_if_id()

        if flush:
            pc = redirect_pc
            next_if_id["instr"] = 0
        elif stall:
            next_if_id = if_id
        else:
            
            if pc not in imem:
                fetching_done = True
            else:
                next_if_id["pc"] = pc
                next_if_id["instr"] = imem[pc]
                next_if_id["valid"] = 1
                pc = pc + 4
        # ------------------------------------------------------------
        # Trace line for this cycle (must be readable)
        # ------------------------------------------------------------
        trace_lines.append(trace_cycle(cycle, pc, stall, flush, next_if_id, next_id_ex, next_ex_mem, next_mem_wb, wb_info))
        
        # ------------------------------------------------------------
        # Latch pipeline registers (end of cycle)
        # ------------------------------------------------------------
        mem_wb = next_mem_wb
        ex_mem = next_ex_mem
        id_ex = next_id_ex
        if_id = next_if_id

        # ------------------------------------------------------------
        # Halt condition: fetch done + pipeline drained
        # ------------------------------------------------------------
        if fetching_done:
            if not (if_id["valid"] or id_ex["valid"] or ex_mem["valid"] or mem_wb["valid"]):
                break
        
        cycle += 1

    # Write logs
    write_trace_log(trace_lines, "trace.log")
    write_regs_log(regs, "regs_final.log")
    write_dmem_log(dmem, "dmem_final.log")

    print("HALT")
    print("cycles =", cycle)
    print("wrote trace.log, regs_final.log, dmem_final.log")


if __name__ == "__main__":
    main()
