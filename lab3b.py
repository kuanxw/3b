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

unallocated_inode_nos = []
allocated_inodes = []

errors = 0

level_string = ["", "INDIRECT ", "DOUBLE INDIRECT ", "TRIPLE INDIRECT "]

#SuperBlock class
class SuperBlock:
    def __init__(self, row):
        self.n_blocks = int(row[1])
        self.n_inodes = int(row[2])
        self.block_size = int(row[3])
        self.inode_size = int(row[4])
        self.blocks_per_group = int(row[5])
        self.inodes_per_group = int(row[6])
        self.first_inode = int(row[7])

#Inode
class Inode:
    def __init__(self, row):
        self.inode_no = int(row[1],16)
        self.file_type = int(row[2],16)
        self.mode = int(row[3],16)
        self.owner = int(row[4],16)
        self.group = int(row[5],16)
        self.link_count = int(row[6],16)
        #self.ctime = int(row[7],16)
        #self.mtime = int(row[8],16)
        #self.atime = int(row[9],16)
        self.size = int(row[10],16)
        self.n_blocks = int(row[11],16)
        self.blocks = map(int, row[12:24])
        self.single_ind = int(row[24],16)
        self.double_ind = int(row[25],16)
        self.triple_ind = int(row[26],16)


#Indirect
class Indirect:
    def __init__(self, row):
        self.inode_no = int(row[1],16)
        self.level = int(row[2],16)
        self.offset = int(row[3],16)
        self.block_no = int(row[4],16)
        self.reference_no = int(row[5],16)

#Dirent
class Dirent:
    def __init__(self, row):
        self.parent_inode = int(row[1],16)
        self.size = int(row[2],16)
        self.entry_inode_num = int(row[3],16)
        self.entry_rec_len = int(row[4],16)
        self.entry_name_len = int(row[5],16)
        self.entry_file_name = row[6].rstrip()

#Print error message
def print_error(message):
    sys.stderr.write(message)
    exit(1)


def parse_csv(file):
    global sb, free_blocks, free_inodes, inodes, indirects

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
            pass
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

#Audit the blocks
def audit_blocks():
    blocks = {}
    global errors

    if block != 0:
        #Check for an invalid block
        if block > sb.n_blocks - 1:
            print("INVALID {}BLOCK {} IN INODE {} AT OFFSET {}".format(level_string[level], block, inode_no, offset))
            errors = errors + 1

        #Check for reserved block
        elif block < 8:
            print("RESERVED {}BLOCK {} IN INODE {} AT OFFSET {}".format(level_string[level], block, inode_no, offset))
            error = errors + 1
            
        #Check for valid block and add it to the block reference count
        elif block in block_refs:
            block_refs[block].append(level, offset, inode_no)
        else:
            block_refs[block] = [(level, offset, inode_no)]

    #Investigate direct block pointers in inodes
    for inode in inodes:
        for offset, block in enumerate(inode.blocks):
            check_block(block, inode.inode_no, offset, 0)
        check_block(inode.single_ind, inode.inode_no, 12, 1)
        check_block(inode.double_ind, inode.inode_no, 268, 2)
        check_block(inode.triple_ind, inode.inode_no, 65804, 3)

    #Investigate indirect entries
    for ind_block in indirects:
        check_block(ind_block.reference_no, ind_block.inode_no, ind_block.offset, ind_block.level)

    #Iterate through all nonreserved data blocks
    for block in range(8, sb.n_blocks):
        if block not in free_blocks and block not in block_refs:
            print("UNREFERENCED BLOCK {}".format(block))
            errors = errors + 1
        elif block in free_blocks and block in block_refs:
            print("ALLOCATED BLOCK {} ON FREELIST".format(block))
            errors = errors + 1
        elif block in block_refs and len(block_refs[block]) > 1:
            inode_refs = block_refs[block]
            for level, offset, inode_no in inode_refs:
                print("DUPLICATE {}BLOCK {} IN INODE {} AT OFFSET {}".format(level_string[level], block, inode_no, offset))
                errors = errors + 1

#Audit inodes
def audit_inodes():
    global errors, inodes, allocated_inodes, unallocated_inode_nos

    unallocated_inode_nos = free_inodes

    for inode in inodes:
        if inode.file_type == '0':
            print("UNALLOCATED INODE {} NOT ON FREELIST".format(inode.inode_no))
            errors = errors + 1
            unallocated_inode_nos.append(inode.inode_no)
        else:
            if inode.inode_no in free_inodes:
                print("ALLOCATED INODE {} ON FREELIST".format(inode.inode_no))
                errors = errors + 1
                unallocated_inode_nos.remove(inode.inode_no)

            allocated_inodes.append(inode)

    for inode in range(sb.first_inode, sb.n_inode):
        used = True if len(list(filter(lambda x: x.inode_no == inode, inodes))) > 0 else False
        if inode not in free_inodes and not used:
            print("UNALLOCATED INODE {} NOT ON FREELIST".format(inode))
            errors = errors + 1
            unallocated_inode_nos.append(inode)


#Check links function
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

#Audit dirents
def audi_dirents():
    global errors
    total_inodes = sb.n_inodes
    inode_link_map = {}

    for dirent in dirents:
        if dirent.entry_inode_num > total_inodes:
            print("DIRECTORY INODE {} NAME {} INVALID INODE {}".format(dirent.parent_inode, dirent.entry_file_name, dirent.entry_inode_num))
            errors = errors + 1
        elif dirent.entry_inode_num in unallocated_inode_nos:
            print("DIRECTORY INODE {} NAME {} UNALLOCATED INODE {}".format(dirent.parent_inode, dirent.entry_file_name, dirent.entry_inode_num))
            errors = errors + 1
        else:
            inode_link_map[dirent.entry_inode_num] = inode_link_map.get(dirent.entry_inode_num, 0) + 1

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
            


