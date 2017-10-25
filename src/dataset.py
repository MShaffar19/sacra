import os, time, datetime, csv, sys, json
import cfg
from Bio import SeqIO
sys.path.append('')

class Dataset:
    '''
    Defines 'Dataset' class, containing procedures for uploading documents from un-cleaned FASTA files
    and turning them into rich JSONs that can be:
        - Uploaded to the fauna database
        - imported directly by augur (does not take JSONs at this time, instead needs FASTAs)

    Each instance of a Dataset contains:
        1. metadata: list of high level information that governs how the data contained in the Dataset
        are treated by Dataset cleaning functions (TODO: Make these in external scripts as a library of
        functions that can be imported by the Dataset), as well as the exact location in the fauna
        database where the dataset should be stored (TODO: specify in a markdown file somewhere exactly
        what the fauna db should look like).

        ex. [FIGURE OUT WHAT THIS WILL LOOK LIKE]

        2. dataset: A list of dictionaries, each one identical in architecture representing 'documents'
        that are contained within the Dataset. These dictionaries represent both lower-level metadata,
        as well as the key information (sequence, titer, etc) that is being stored/run in augur.

        ex. [ {date: 2012-06-11, location: Idaho, sequence: GATTACA}, {date: 2016-06-16, location: Oregon, sequence: CAGGGCCTCCA}, {date: 1985-02-22, location: Brazil, sequence: BANANA} ]
    '''
    def __init__(self, datatype, virus, outpath, **kwargs):
        # Wrappers for data, described in class description
        self.metadata = {'datatype': datatype, 'virus': virus}
        self.dataset = {}

        self.read_metadata(**kwargs)

        # Track which documents should be removed
        self.bad_docs = []

        self.read_data_files(datatype, **kwargs)
        self.remove_seed()
        t = time.time()
        for key in self.dataset.keys():
            self.clean(key, self.dataset[key])
        self.remove_bad_docs()
        print '~~~~~ Cleaned %s documents in %s seconds ~~~~~' % (len(self.dataset), (time.time()-t))
        self.compile_virus_table(**kwargs)
        self.build_references_table()

    def read_data_files(self, datatype, infiles, ftype, **kwargs):
        '''
        Look at all infiles, and determine what file type they are. Based in that determination,
        import each file individually.
        '''
        t = time.time()
        if datatype == 'sequence':
            fasta_suffixes = ['fasta', 'fa', 'f']
            # Set fields that will be used to key into fauna table, these should be unique for every document
            self.index_fields = ['accession']
            if ftype.lower() in fasta_suffixes:
                for infile in infiles:
                    self.read_fasta(infile, datatype=datatype, **kwargs)
            else:
                pass
        print '~~~~~ Read %s file(s) in %s seconds ~~~~~' % (len(infiles), (time.time()-t))

    def read_fasta(self, infile, source, path, datatype, **kwargs):
        '''
        Take a fasta file and a list of information contained in its headers
        and build a dataset object from it.
        '''
        import cleaning_functions as cf
        print 'Reading in %s FASTA from %s%s.' % (source,path,infile)
        self.fasta_headers = cfg.fasta_headers[source.lower()]
        self.seed(datatype)

        out = []

        # Read the fasta
        with open(path + infile, "rU") as f:

            for record in SeqIO.parse(f, "fasta"):
                data = {}
                head = record.description.replace(" ","").split('|')
                for i in range(len(self.fasta_headers)):
                    data[self.fasta_headers[i]] = head[i]
                    data['sequence'] = str(record.seq)

                index = []
                for ind in self.index_fields:
                    try:
                        index.append(data[ind])
                    except:
                        pass
                out.append({":".join(index): data})

        # Merge the formatted dictionaries to self.dataset()
        print 'Fixing names for new documents'
        t = time.time()
        cf.format_names(out, self.metadata['virus'])
        print '~~~~~ Fixed names in %s seconds ~~~~~' % (time.time()-t)

        print 'Merging input FASTA to %s documents.' % (len(out))
        for doc in out:
            try:
                assert isinstance(doc, dict)
            except:
                print 'WARNING: Cannot merge doc of type %s: %s' % (type(doc), (str(doc)[:75] + '..') if len(str(doc)) > 75 else str(doc))
                pass
            assert len(doc.keys()) == 1, 'More than 1 key in %s' % (doc)
            self.merge(doc.keys()[0], doc[doc.keys()[0]])
        print 'Successfully merged %s documents. Done reading %s.' % (len(self.dataset)-1, infile)


    def read_metadata(self, path, metafile, **kwargs):
        '''
        Read an xml file to a metadata dataset
        '''
        if metafile is not None:
            import pandas as pd
            xl = pd.ExcelFile(path + metafile)
            meta = xl.parse("Tabelle1")
            print meta.columns
            meta.columns = [x.lower() for x in meta.columns]
            print meta.columns
            for index, row in meta.iterrows():
                # TODO: this
                pass

    def merge(self, key, data):
        '''
        Make sure all new entries to the dataset have formatted names
        '''
        self.dataset[key] = data

    def clean(self, key, doc):
        '''
        Take a document and return a canonicalized version of that document
        # TODO: Incorporate all the necessary cleaning functions
        '''
        # Remove docs with bad keys or that are not of type dict
        try:
            assert isinstance(doc, dict)
        except:
            print 'Documents must be of type dict, this one is of type %s:\n%s' % (type(doc), doc)
            return

        k = doc.keys()[0]

        # Use functions specified by cfg.py. Fxn defs in cleaning_functions.py
        if self.metadata['datatype'] == 'sequence':
            fxns = cfg.sequence_clean
        elif self.metadata['datatype'] == 'titer':
            fxns = cfg.titer_clean

        for fxn in fxns:
            fxn(doc, key, self.bad_docs, self.metadata['virus'])

    def remove_bad_docs(self):

        # Not working because of key errors, they should be ints
        if self.bad_docs != []:
            print 'Documents that need to be removed : %s ' % (self.bad_docs)
            self.bad_docs = self.bad_docs.sort().reverse()
            for key in self.bad_docs:
                t = self.dataset[key]
                self.dataset[key] = self.dataset[-1]
                self.dataset[-1] = t
                self.dataset.pop()

    def write(self, out_file):
        '''
        Write self.dataset to an output file, default type is json
        '''
        print 'Writing dataset to %s' % (out_file)
        t = time.time()
        out = {}
        for key in self.metadata.keys():
            out[key] = self.metadata[key]
        out['data'] = self.dataset
        out['viruses'] = self.viruses
        out['references'] = self.references

        with open(out_file, 'w+') as f:
            json.dump(out, f, indent=1)
	    print '~~~~~ Wrote output in %s seconds ~~~~~' % (time.time()-t)

    def seed(self, datatype):
        '''
        Make an empty entry in dataset that has all the necessary keys, acts as a merge filter
        '''
        seed = { field : None for field in cfg.optional_fields[datatype] }
        seed['sequence'] = None
        print 'Seeding with:'
        print seed
        self.dataset['seed'] = seed

    def remove_seed(self):
        # More efficient on large datasets than self.dataset = self.dataset[1:]
        self.dataset.pop('seed',None)
        # self.dataset[0] = self.dataset[-1]
        # self.dataset[-1] = t
        # self.dataset = self.dataset[:-1]

    def set_sequence_permissions(self, permissions, **kwargs):
        for a in self.dataset:
            self.dataset[a]['permissions'] = permissions

    def compile_virus_table(self, subtype, **kwargs):
        vs = {}
        for virus in self.dataset.keys():
            # Initialize virus dict
            name = self.dataset[virus]['strain']
            if name not in vs.keys():
                vs[name] = {'strain' : name }
            if 'accessions' in vs[name].keys():
                vs[name]['accessions'].append(self.dataset[virus]['accession'])
            else:
                vs[name]['accessions'] = [self.dataset[virus]['accession']]

            # Scrape virus host
            # TODO: Resolve issues if there are different hosts
            if 'host' not in self.dataset[virus].keys():
                vs[name]['host'] = 'human'
            elif self.dataset[virus]['host'] == None:
                vs[name]['host'] = 'human'
                self.dataset[virus].pop('host',None)
            else:
                vs[name]['host'] = name['host']
                self.dataset[virus].pop('host',None)

            # Scrape host age
            # TODO: Resolve issues if there are different ages
            if 'age' not in self.dataset[virus].keys():
                vs[name]['host_age'] = None
            elif self.dataset[virus]['age'] == None:
                vs[name]['host_age'] = None
                self.dataset[virus].pop('age',None)
            else:
                vs[name]['host_age'] = name['age']
                self.dataset[virus].pop('age',None)

            # Scrape subtype
            if subtype != None:
                vs[name]['subtype'] = subtype
            elif ('subtype' in self.dataset[virus].keys()) and (self.dataset[virus]['subtype'] is not None):
                vs[name]['subtype'] = self.dataset[virus]['subtype']
                self.dataset[virus].pop('subtype', None)
            else:
                vs[name]['subtype'] == None

        for name in vs.keys():
            # Scrape number of segments
            segments = set()
            for a in vs[name]['accessions']:
                segments.add(self.dataset[a]['locus'])
            vs[name]['number_of_segments'] = len(segments)

            # # Scrape isolate ids
            # ids = set()
            # for a in vs[name]['accessions']:
            #     ids.add(self.dataset[a]['isolate_id'])
            # vs[name]['isolate_ids'] = list(ids)

            # Placeholder for un_locode
            vs[name]['un_locode'] = 'placehoder'
            # location = name.split('/')[1]
            # vs[name]['un_locode'] = lookup_locode(location) TODO: Write this fxn

        self.viruses = vs

    def build_references_table(self):
        '''
        This is a placeholder function right now, it will build a reference
        table for each upload according to the spec:
        {
        "pubmed_id" : {
          "authors" : [
            "author1",
            "author2",
            "author3"
          ],
          "journal" : "journal name",
          "date" : "publication date",
          "accessions" : [
            "accession1",
            "accession2",
            "accession3"
          ],
          "publication_name" : "name"
        }
        '''
        refs = {
        "pubmed_id" : {
          "authors" : [
            "author1",
            "author2",
            "author3"
          ],
          "journal" : "journal name",
          "date" : "publication date",
          "accessions" : [
            "accession1",
            "accession2",
            "accession3"
          ],
          "publication_name" : "name"
        } }

        self.references = refs
