I created these tools to help me fill out a database, The data contains regions and pin codes across india ideal for use
in scraping data and being flexible about it.

It's a simple python CLI program and does the following things:

- state : Prints all states. ( STATES )
- districts : Prints all districts ( State | District )
- post offices: Prints all post offices. ( District | Region )
- areas : Prints all areas and their pin codes. ( Region | Pincode | Type | Delivery )

This is very customizable, also flexible with the dataset. However note that I have a small set and I have used the
titles as a key. This would be very tedious to use with extremely large sets.
