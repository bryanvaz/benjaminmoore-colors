import argparse
import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
import yaml
import struct 

class BMColors:

    # Default location of the Benjamin Moore color collections containing ase files.
    default_ase_collections_url = 'https://www.benjaminmoore.com/en-us/architects-designers/download-benjamin-moore-color-palettes'
    
    default_collections_filename = "collections_data.yaml"

    default_output_filename_yaml = "benjaminmoore-colors.yaml"

    def __init__(self, options={}):
        # TODO: Fill in the comments for the constructor.
        self.options = options

        # set the ase_collections_url to the default if it is not set in the options
        self.ase_collections_url = options.get('ase_collections_url', self.default_ase_collections_url)

        # set the workspace directory to the default if it is not set in the options
        self.workspace_dir = options.get('workspace_dir', 'workspace')

        self.collections_data = []

        self.parsed_colors = {}
    

    def scrape_collections(self):
        """
        Scrapes the Benjamin Moore website to get all available color collections.
        Saves the data to the workspace directory
        """
        # prepare the workspace
        self._prepare_workspace()

        # URL of the website
        url = self.ase_collections_url

        print("Scraping: ", url)

        # Send a GET request to the website
        response = requests.get(url)

        # Create a BeautifulSoup object to parse the HTML content
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all <a> tags that end in ".ase"
        ase_links = soup.find_all("a", href=lambda href: href and href.endswith(".ase"))

        print(f"Found {len(ase_links)} links to .ase files.")

        # Save each collection name and the link to its .ase file
        for link in ase_links:
            file_url = urllib.parse.urljoin(url, link["href"])
            # get the text of the link
            collection_name = link.text
            file_name = link["href"].split("/")[-1]  # Extract the file name from the URL
            
            # check if the file_name already exists in self.collections_data
            # if it does, then append overwrite the entry in the list, otherwise append
            collection_exists = False
            for collection in self.collections_data:
                if collection['file_name'] == file_name:
                    collection['collection_name'] = collection_name
                    collection['file_url'] = file_url
                    collection_exists = True
                    break
            if not collection_exists:
                self.collections_data.append({
                    "collection_name": collection_name,
                    "file_name": file_name,
                    "file_url": file_url
                })

        print(f"Found {len(self.collections_data)} collections.")
        # write the collections data to the workspace
        self.save_collections_data_to_workspace()

    def download_ase_files(self):
        """
        Downloads all ase files.
        :param collection_name: The name of the color collection to download.
        """

        # prepare the workspace
        self._prepare_workspace()

        print(f"Downloading {len(self.collections_data)} .ase files.")

        # Download each .ase file
        for collection in self.collections_data:
            print("Downloading:", collection['file_name'])

            # Send a GET request to download the file
            file_response = requests.get(collection['file_url'])
            
            # Save the file to the workspace folder
            with open(os.path.join(self.workspace_dir, collection['file_name']), "wb") as file:
                file.write(file_response.content)
        
        print("Download complete.")
    
    def parse_all_ase_files_in_workspace(self):
        """
        Parses all the ase files in the workspace.
        """
        # prepare the workspace
        self._prepare_workspace()

        # parse all the ase files in the workspace
        for file_name in os.listdir(self.workspace_dir):
            if file_name.endswith(".ase"):
                self.parse_ase_file_by_name(file_name)
        
        self.save_parsed_colors_to_yaml_workspace()

    def parse_ase_file_by_name(self, file_name):
        """
        Parses the ase file with the given file_name in the workspace.
        :param file_name: The name of the ase file to parse.
        :return: A list of color objects.
        """

        # check if file_name exists in the workspace
        file_path = os.path.join(self.workspace_dir, file_name)
        if not os.path.exists(file_path):
            raise Exception(f"File '{file_path}' does not exist.")

        return self.parse_ase_file(file_path)

    def parse_ase_file(self, file_path):
        """
        Parses the ase file and returns a list of color objects.
        
        The parsed colors are also stored in the self.parsed_colors dictionary.
        The key is the file_name and the value is the list of parsed colors.

        Args:
            file_path (str): The path to the ase file to parse.
        """
        
        # prepare the workspace
        self._prepare_workspace()
        
        # check if file_path exists
        if not os.path.exists(file_path):
            raise Exception(f"File '{file_path}' does not exist.")
        
        # read in the file into a bytes object
        with open(file_path, "rb") as f:
            ase_data = f.read()
        
        print(f"Parsing {file_path} ...")

        # parse the bytes object into a list of colors
        this_parsed_colors = self.parse_ase_data(ase_data)

        print(f"Found {len(this_parsed_colors)} colors.")

        # store the parsed colors in the self.parsed_colors dictionary
        self.parsed_colors[os.path.basename(file_path)] = this_parsed_colors

        return this_parsed_colors

    def parse_ase_data(self, byte_data, debug=False):
        """
        Parses the ase file and returns a list of color objects.

        Args:
            byte_data (bytes): The bytes of the ase file to parse.
            debug (bool, optional): Whether to print debug statements. Defaults to False.
        """
        pointer = 4  # Skip the "ASEF" header
        major_version, minor_version, num_chunks = struct.unpack_from("!HHI", byte_data, pointer)

        print(f"Major version: {major_version}, Minor version: {minor_version}, Number of chunks: {num_chunks}") if debug else None
        pointer += 8

        colors = []
        for _ in range(num_chunks):
            print(f"Processing chunk {_}/{num_chunks}. pointer at {pointer}/{len(byte_data)}") if debug else None
            chunk_type, = struct.unpack_from(">H", byte_data, pointer)
            pointer += 2

            chunk_size, = struct.unpack_from(">I", byte_data, pointer)
            pointer += 4

            chunk_end = pointer + chunk_size
            chunk = byte_data[pointer:pointer + chunk_size]
            pointer = chunk_end  # Move to the next chunk no matter what

            if chunk_type == 0xc001:  # Palette
                print(f"Palette chunk... skipping to {chunk_end}") if debug else None
                continue
            
            if chunk_type == 0xc002:  # Palette End
                print(f"Palette end chunk... skipping to {chunk_end}") if debug else None
                continue

            if chunk_type == 0x0001:  # Color entry
                print(f"Processing color... chunk length: {chunk_size}") if debug else None
                
                chunk_pointer = 0
                title_length, = struct.unpack_from(">H", chunk, chunk_pointer)
                chunk_pointer += 2
                
                # Decode the color name
                title_raw, = struct.unpack_from(f"!{title_length*2}s", chunk, chunk_pointer)

                # title = title_raw.decode('utf-8', 'ignore')
                title = title_raw.decode("utf-16be").strip('\0')
                

                print(f"Color '{title}' found.") if debug else None

                color_data = chunk[2 + title_length*2:]  

                # Decode the color mode
                color_mode = struct.unpack_from(f"!4s", color_data)[0].strip()

                # Decode the color values
                fmt = {b'RGB': '!fff', b'Gray': '!f', b'CMYK': '!ffff', b'LAB': '!fff'}
                color_values = list(struct.unpack(fmt[color_mode], color_data[4:-2]))
                
                # Decode the color type
                color_types = ['Global', 'Spot', 'Process']
                swatch_type_index = struct.unpack(">h", color_data[-2:])[0]
                swatch_type = color_types[swatch_type_index]

                color = {
                    'name': title,
                    'swatch_type': swatch_type,
                    'data': {
                        'mode': color_mode.decode('utf-8'),
                        'values': color_values
                    }
                }
                colors.append(color)

                print(f"Processed '{color['name']}' - {color['data']['mode']} - {color['data']['values']}") if debug else None
        
        return colors

    def _prepare_workspace(self):
        """
        Prepares the workspace for the scraper.
        """
        # Prepare a workspace folder
        os.makedirs("workspace", exist_ok=True)

    def save_collections_data_to_workspace(self):
        """
        Writes the collections data to the workspace.
        """
        # prepare the workspace
        self._prepare_workspace()
        file_name = os.path.join(self.workspace_dir, self.default_collections_filename)
        with open(file_name, "w") as f:
            yaml.dump(self.collections_data, f)
        
        print(f"Saved collections url data to '{file_name}'")

    def load_collections_data_from_workspace(self):
        """
        Reads the collections data from the workspace and sto
        """
        # Check if collections file exists
        if not os.path.exists(os.path.join(self.workspace_dir, self.default_collections_filename)):
            return

        with open(os.path.join(self.workspace_dir, self.default_collections_filename), "r") as f:
            collections_data = yaml.safe_load(f)
        self.collections_data = collections_data

    def save_parsed_colors_to_yaml_workspace(self):
        """
        Writes the parsed colors to the workspace.
        """
        # prepare the workspace
        self._prepare_workspace()

        output_filepath = os.path.join(self.workspace_dir, self.default_output_filename_yaml)

        print(f"Saving parsed colors to '{output_filepath}'")
        with open(output_filepath, "w") as f:
            yaml.dump(self.parsed_colors, f)

        print(f"Saved parsed colors to '{output_filepath}'")
    
    
def main():
    parser = argparse.ArgumentParser(description='Scrape, download and parse all ase files for Benjamin Moore color collections.')
    parser.add_argument('--scrape', action='store_true', help='Scrape the Benjamin Moore website to get all available color collections.')
    # parser.add_argument('--download', help='Download all ase files for a given color collection.')
    parser.add_argument('--parse', help='Parse all ase files and save to workspace.')
    parser.add_argument('--all', help='Parse all ase files and save to workspace.')
    args = parser.parse_args()

    bm_colors = BMColors()

    if args.scrape:
        bm_colors.scrape_collections()
        bm_colors.download_ase_files()
    elif args.parse:
        bm_colors.parse_all_ase_files_in_workspace()
    elif args.all:
        bm_colors.scrape_collections()
        bm_colors.download_ase_files()
        bm_colors.parse_all_ase_files_in_workspace()
    elif args.help:
        parser.print_help()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()