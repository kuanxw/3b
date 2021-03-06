#!/usr/bin/python

#NAME: Amir Saad, Kuan Xiang Wen
#EMAIL: arsaad@g.ucla.edu, kuanxw@g.ucla.edu
#ID: 604840359, 004461554

import sys
import csv
import os

sb = None
free_blocks = []
free_inodes = []
inodes = []
indirects = []
dirents = []
pointer_counter = []

unallocated_inode_nos = []
allocated_inodes = []
reserved_blocks_end = -1

errors = 0

level_string = ["", "INDIRECT ", "DOUBLE INDIRECT ", "TRIPLE INDIRECT "]

#SuperBlock class
class SuperBlock:
    def __init__(self, row):
        self.n_blocks = int(row[1])
        self.n_inodes = int(row[2])
        self.block_size = int(row[3])
        self.inode_size = int(row[4])
        #self.blocks_per_group = int(row[5])
        #self.inodes_per_group = int(row[6])
        self.first_inode = int(row[7])

#Inode
class Inode:
    def __init__(self, row):
        self.inode_no = int(row[1])
        self.file_type = row[2].rstrip()
        #self.mode = int(row[3])
        #self.owner = int(row[4])
        #self.group = int(row[5])
        self.link_count = int(row[6])
        #self.ctime = int(row[7])
        #self.mtime = int(row[8])
        #self.atime = int(row[9])
        #self.size = int(row[10)
        self.n_blocks = int(row[11])
        self.blocks = list(map(int, row[12:24]))
        self.single_ind = int(row[24])
        self.double_ind = int(row[25])
        self.triple_ind = int(row[26])

#Indirect
class Indirect:
    def __init__(self, row):
        self.inode_no = int(row[1])
        self.level = int(row[2])
        self.offset = int(row[3])
        self.block_no = int(row[4])
        self.reference_no = int(row[5])

#Dirent
class Dirent:
    def __init__(self, row):
        self.parent_inode = int(row[1])
        #self.size = int(row[2],16)
        self.entry_inode_num = int(row[3])
        #self.entry_rec_len = int(row[4],16)
        #self.entry_name_len = int(row[5],16)
        self.entry_file_name = row[6].rstrip()

#Print error message
def print_error(message):
    sys.stderr.write(message)
    exit(1)


def parse_csv(file):
    global sb, reserved_blocks_end, free_blocks, free_inodes, inodes, indirects

    f = open(file, 'r')

    if not f:
        print_error("Error opening file\n")

    if os.path.getsize(file) <= 0:
        print_error("Error! File is empty\n")

    reader = csv.reader(f)

    for row in reader:
        if len(row) <= 0:
            print_error("Error! File contains a blank line\n")

        category = row[0]

        if category == 'SUPERBLOCK':
            sb = SuperBlock(row)
        elif category == 'GROUP':
            reserved_blocks_end = int(row[8])
        elif category == 'BFREE':
            free_blocks.append(int(row[1]))
        elif category == 'IFREE':
            free_inodes.append(int(row[1]))
        elif category == 'DIRENT':
            dirents.append(Dirent(row))
        elif category == 'INODE':
            inodes.append(Inode(row))
        elif category == 'INDIRECT':
            indirects.append(Indirect(row))
        else:
            print_error("Error! Unrecognized line in the csv file\n")

#check if block is valid, and then add it to our pointer_counter tracking structure
def valid_block_check(level, blocknum, inode, offset):
    global pointer_counter, errors

    if blocknum == 0:
        pass
    elif blocknum > sb.n_blocks - 1 or blocknum < 0:
        print("INVALID {}BLOCK {} IN INODE {} AT OFFSET {}".format(level, blocknum, inode, offset))
        errors = errors + 1
    elif blocknum < reserved_blocks_end:
        print("RESERVED {}BLOCK {} IN INODE {} AT OFFSET {}".format(level, blocknum, inode, offset))
        errors = errors + 1
    else:
        #Valid block, so log it
        if pointer_counter[blocknum] == -1:
            pointer_counter[blocknum] = [[level,inode,offset]]
        else:
            pointer_counter[blocknum].append([level,inode,offset])

#Block consistency audit
def audit_blocks():
    #Tracks all pointers to each block. eg. pointers to block 76 stored in pointer_counter[76]
    #Value: -1 if no pointer, a list of lists otherwise, where each list stores:
    #[indirection level of inode with that pointer, inode with that pointer, offset of the block]
    global pointer_counter, errors
    pointer_counter = [-1]*sb.n_blocks

    #check direct blocks
    for inode in inodes:
        for blocknum in inode.blocks:
            valid_block_check(level_string[0], blocknum, inode.inode_no, 0)
        valid_block_check(level_string[1],inode.single_ind, inode.inode_no, 12)
        valid_block_check(level_string[2],inode.double_ind, inode.inode_no, 268)
        valid_block_check(level_string[3],inode.triple_ind, inode.inode_no, 65804)
    
    #check indirect blocks
    for indirect in indirects:
        valid_block_check(level_string[indirect.level], indirect.reference_no, indirect.inode_no, indirect.offset)
        
    #add free blocks and inodes while checking for allocated free blocks
    for free_block in free_blocks:
        if(pointer_counter[free_block] == -1):
            pointer_counter[free_block] = 0
        else:
            print("ALLOCATED BLOCK {} ON FREELIST".format(free_block))
            errors = errors + 1
                
    #check for unreferenced and duplicate blocks
    for blocknum,blockentries in enumerate(pointer_counter):
        #skip if 1) block is correctly free 2) this is a reserved inode
        if(blockentries == 0):
            pass
        elif(blockentries == -1 and blocknum < sb.n_inodes  + 1):
            pass
        #blocks
        elif(blockentries == -1):
            print("UNREFERENCED BLOCK {}".format(blocknum))
            errors = errors + 1
        elif len(blockentries) > 1:
            for item in blockentries:
                print("DUPLICATE {}BLOCK {} IN INODE {} AT OFFSET {}".format(item[0], pointer_counter.index(pointer_counter[blocknum]), item[1], item[2]))
                errors = errors + 1
    
#Inode allocation audit
def audit_inodes():
    global errors, inodes, allocated_inodes, unallocated_inode_nos

    unallocated_inode_nos = free_inodes

    #Appending inodes to allocated_inodes list. Error if on freelist
    for inode in inodes:
        #First if statement for redundancy
        if inode.file_type == '0':
            if inode.inode_no not in free_inodes:
                print("UNALLOCATED INODE {} NOT ON FREELIST".format(inode.inode_no))
                errors = errors + 1
                unallocated_inode_nos.append(inode.inode_no)
        else:
            if inode.inode_no in free_inodes:
                print("ALLOCATED INODE {} ON FREELIST".format(inode.inode_no))
                errors = errors + 1
                unallocated_inode_nos.remove(inode.inode_no)

            allocated_inodes.append(inode)

    #Check all inodes if free/allocated or unallocated
    for inode in range(sb.first_inode, sb.n_inodes):
        used = True if len(list(filter(lambda x: x.inode_no == inode, inodes))) > 0 else False
        if inode not in free_inodes and not used:
            print("UNALLOCATED INODE {} NOT ON FREELIST".format(inode))
            errors = errors + 1
            unallocated_inode_nos.append(inode)


#Check self and parent links
def check_links():
    global errors
    inode_to_parent = {2: 2}

    for dirent in dirents:
        if dirent.entry_inode_num <= sb.n_inodes and dirent.entry_inode_num not in unallocated_inode_nos:
            if dirent.entry_file_name != "'..'" and dirent.entry_file_name != "'.'":
                inode_to_parent[dirent.entry_inode_num] = dirent.parent_inode

    for dirent in dirents:
        if dirent.entry_file_name == "'.'":
            if dirent.entry_inode_num != dirent.parent_inode:
                print("DIRECTORY INODE {} NAME '.' LINK TO INODE {} SHOULD BE {}".format(dirent.parent_inode, dirent.entry_inode_num, dirent.parent_inode))
                errors = errors + 1
        elif dirent.entry_file_name == "'..'":
            if dirent.entry_inode_num != inode_to_parent[dirent.parent_inode]:
                print("DIRECTORY INODE {} NAME '..' LINK TO INODE {} SHOULD BE {}".format(dirent.parent_inode, dirent.entry_inode_num, inode_to_parent[dirent.parent_inode]))
                errors = errors + 1

#Directory consistency audit
def audit_dirents():
    global errors
    total_inodes = sb.n_inodes
    inode_link_map = {}

    #Check directory for validity and allocation of each referenced I-node
    for dirent in dirents:
        if dirent.entry_inode_num > total_inodes:
            print("DIRECTORY INODE {} NAME {} INVALID INODE {}".format(dirent.parent_inode, dirent.entry_file_name, dirent.entry_inode_num))
            errors = errors + 1
        elif dirent.entry_inode_num in unallocated_inode_nos:
            print("DIRECTORY INODE {} NAME {} UNALLOCATED INODE {}".format(dirent.parent_inode, dirent.entry_file_name, dirent.entry_inode_num))
            errors = errors + 1
        else:
            inode_link_map[dirent.entry_inode_num] = inode_link_map.get(dirent.entry_inode_num, 0) + 1

    #Check if count of directory links and inode linkcount matches
    for inode in allocated_inodes:
        if inode.inode_no in inode_link_map:
            if inode.link_count != inode_link_map[inode.inode_no]:
                print("INODE {} HAS {} LINKS BUT LINKCOUNT IS {}".format(inode.inode_no, inode_link_map[inode.inode_no], inode.link_count))
                errors = errors + 1
        else:
            if inode.link_count != 0:
                print("INODE {} HAS 0 LINKS BUT LINKCOUNT IS {}".format(inode.inode_no, inode.link_count))
                errors = errors + 1

    check_links()

if __name__ == '__main__':
    #Check if valid number of arguments is provided
    if(len(sys.argv)) != 2:
        print_error("Correct usage: ./lab3b Filename\n")

    #Read in the file 
    filename = sys.argv[1]

    #Check if file is valid
    if not os.path.isfile(filename):
        print_error("Error! File does not exist\nCorrect usage: ./lab3b Filename\n")

    #Parse file
    parse_csv(filename)

    audit_blocks()
    audit_inodes()
    audit_dirents()
    
    
    exit(2) if errors != 0 else exit(0)
            


